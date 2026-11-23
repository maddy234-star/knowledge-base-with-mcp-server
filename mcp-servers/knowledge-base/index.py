"""SQLite FTS5 chunk index with BM25 ranking and incremental sync. Standard library only.

Design
- Chunks, not files, are the unit of search. A note is split on headings, then packed
  into chunks of at most MAX_CHARS characters.
- Metadata (topic, source, date, tags) lives in real columns on `chunks`, with B-tree
  indexes, so filters run in SQL alongside (or instead of) the full-text match.
- `chunks_fts` is an external-content FTS5 table: the text is stored once, in `chunks`.
  Triggers keep the two in step. Ranking is BM25 with per-column weights.
- `sync()` is incremental. Per file it stores mtime + size + sha256. Unchanged files are
  skipped after a single stat(); touched-but-identical files only refresh their mtime;
  only files whose content hash changed are re-chunked. Deleted files are removed.

Front matter (optional) at the top of a note:

    ---
    topic: mcp
    source: Claude Code in Action course
    date: 2026-10-10
    tags: [mcp, stdio]
    ---

Defaults when absent: topic = first sub-folder under notes/ (else "general"),
source = the file's relative path, date = file modified date, tags = none.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CHUNKER_VERSION = "1"  # bump when chunking/metadata rules change: forces a re-chunk of every file
MAX_CHARS = 900
BM25_WEIGHTS = (4.0, 1.0, 2.0)  # heading, text, tags
MAX_LIMIT = 100

ROOT = Path(__file__).resolve().parents[2]

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "are", "was", "were", "do", "does", "did", "how", "what", "why", "when",
    "i", "my", "me", "it", "this", "that", "about", "can", "use", "using", "learn", "learned",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS files (
    id         INTEGER PRIMARY KEY,
    path       TEXT NOT NULL UNIQUE,      -- relative to the notes dir, posix style
    title      TEXT NOT NULL,
    mtime_ns   INTEGER NOT NULL,
    size       INTEGER NOT NULL,
    sha256     TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    n_chunks   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id       INTEGER PRIMARY KEY,
    file_id  INTEGER NOT NULL,
    chunk_no INTEGER NOT NULL,
    heading  TEXT NOT NULL,
    text     TEXT NOT NULL,
    topic    TEXT NOT NULL COLLATE NOCASE,
    source   TEXT NOT NULL COLLATE NOCASE,
    date     TEXT NOT NULL,               -- ISO YYYY-MM-DD
    tags     TEXT NOT NULL                -- space separated, searchable via FTS
);
CREATE INDEX IF NOT EXISTS idx_chunks_file   ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_topic  ON chunks(topic);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);
CREATE INDEX IF NOT EXISTS idx_chunks_date   ON chunks(date);

-- normalised tags, for exact "has all of these tags" filtering
CREATE TABLE IF NOT EXISTS chunk_tags (
    tag      TEXT NOT NULL,
    chunk_id INTEGER NOT NULL,
    PRIMARY KEY (tag, chunk_id)
) WITHOUT ROWID;

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    heading, text, tags,
    content='chunks', content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2',
    prefix='2 3'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, heading, text, tags) VALUES (new.id, new.heading, new.text, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, heading, text, tags)
        VALUES ('delete', old.id, old.heading, old.text, old.tags);
    DELETE FROM chunk_tags WHERE chunk_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, heading, text, tags)
        VALUES ('delete', old.id, old.heading, old.text, old.tags);
    INSERT INTO chunks_fts(rowid, heading, text, tags) VALUES (new.id, new.heading, new.text, new.tags);
END;
"""


# --------------------------------------------------------------------------- paths


def default_notes_dir() -> Path:
    return Path(os.environ.get("KB_NOTES_DIR", ROOT / "notes")).expanduser().resolve()


def default_db_path(notes_dir: Path) -> Path:
    env = os.environ.get("KB_INDEX_PATH")
    return Path(env).expanduser().resolve() if env else Path(notes_dir).resolve().parent / ".kb" / "index.db"


# --------------------------------------------------------------------------- parsing & chunking

_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class Chunk:
    heading: str
    text: str


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Return (metadata, body). Understands simple `key: value` lines only."""
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip().strip("'\"")
    return meta, text[m.end():]


def parse_tags(value: str) -> list[str]:
    value = value.strip().strip("[]")
    tags = [t.strip().strip("'\"#").lower() for t in value.split(",")]
    return list(dict.fromkeys(t for t in tags if t))


def _split_long(paragraph: str) -> list[str]:
    out: list[str] = []
    cur = ""
    for piece in re.split(r"(?<=[.!?])\s+|\n", paragraph):
        while len(piece) > MAX_CHARS:
            if cur:
                out.append(cur)
                cur = ""
            out.append(piece[:MAX_CHARS])
            piece = piece[MAX_CHARS:]
        if cur and len(cur) + 1 + len(piece) > MAX_CHARS:
            out.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}" if cur else piece
    if cur:
        out.append(cur)
    return out


def _pack(text: str) -> list[str]:
    """Pack paragraphs into pieces of at most MAX_CHARS, splitting oversized paragraphs."""
    pieces: list[str] = []
    for para in (p.strip() for p in re.split(r"\n\s*\n", text)):
        if para:
            pieces.extend([para] if len(para) <= MAX_CHARS else _split_long(para))
    out: list[str] = []
    cur = ""
    for piece in pieces:
        if cur and len(cur) + 2 + len(piece) > MAX_CHARS:
            out.append(cur)
            cur = piece
        else:
            cur = f"{cur}\n\n{piece}" if cur else piece
    if cur:
        out.append(cur)
    return out


def chunk_markdown(body: str, fallback_heading: str) -> list[Chunk]:
    """Split on headings (ignoring '#' inside code fences); each chunk carries its heading path."""
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        text = "\n".join(buf).strip()
        buf.clear()
        if text:
            heading = " > ".join(h for _, h in stack) or fallback_heading
            chunks.extend(Chunk(heading, piece) for piece in _pack(text))

    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2).strip()))
        else:
            buf.append(line)
    flush()
    return chunks


def _doc_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


# --------------------------------------------------------------------------- database


def fts5_available() -> bool:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (creating if needed) the index. Safe for one writer + many readers (WAL)."""
    if not fts5_available():
        raise RuntimeError("This Python's SQLite was built without FTS5.")
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)  # we manage transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-65536")  # 64 MB
    conn.execute("PRAGMA mmap_size=268435456")  # 256 MB
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT value FROM meta WHERE key='chunker_version'").fetchone()
    if row is None or row["value"] != CHUNKER_VERSION:
        # chunking rules changed: invalidate every file so the next sync re-chunks it
        conn.execute("UPDATE files SET mtime_ns=0, sha256=''")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('chunker_version', ?)", (CHUNKER_VERSION,))
    return conn


# --------------------------------------------------------------------------- incremental sync


@dataclass
class SyncStats:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    touched: int = 0  # mtime changed, content identical: not re-chunked
    chunks_written: int = 0
    seconds: float = 0.0

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.removed)

    def summary(self) -> str:
        return (
            f"added={self.added} updated={self.updated} removed={self.removed} "
            f"unchanged={self.unchanged} touched={self.touched} "
            f"chunks_written={self.chunks_written} in {self.seconds * 1000:.0f} ms"
        )


def scan(notes_dir: Path) -> dict[str, tuple[int, int]]:
    """Map relative path -> (mtime_ns, size) for every .md file (hidden dirs/files skipped)."""
    notes_dir = Path(notes_dir)
    found: dict[str, tuple[int, int]] = {}
    for root, dirs, files in os.walk(notes_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.startswith(".") or not name.lower().endswith(".md"):
                continue
            full = os.path.join(root, name)
            try:
                st = os.stat(full)
            except OSError:
                continue  # vanished mid-scan
            rel = os.path.relpath(full, notes_dir).replace(os.sep, "/")
            found[rel] = (st.st_mtime_ns, st.st_size)
    return found


def _index_file(
    conn: sqlite3.Connection, file_id: int | None, rel: str, raw: bytes, mtime_ns: int, size: int, digest: str
) -> int:
    text = raw.decode("utf-8", errors="replace")
    fm, body = parse_front_matter(text)
    stem = Path(rel).stem
    title = _doc_title(body, stem)
    topic = fm.get("topic") or (rel.split("/")[0] if "/" in rel else "general")
    source = fm.get("source") or rel
    date_match = _DATE.search(fm.get("date", ""))
    date = date_match.group(0) if date_match else datetime.fromtimestamp(mtime_ns / 1e9).strftime("%Y-%m-%d")
    tags = parse_tags(fm.get("tags", ""))
    chunks = chunk_markdown(body, title)
    now = datetime.now().isoformat(timespec="seconds")

    if file_id is None:
        file_id = conn.execute(
            "INSERT INTO files(path,title,mtime_ns,size,sha256,indexed_at,n_chunks) VALUES (?,?,?,?,?,?,?)",
            (rel, title, mtime_ns, size, digest, now, len(chunks)),
        ).lastrowid
    else:
        conn.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))  # triggers clean FTS + tags
        conn.execute(
            "UPDATE files SET title=?, mtime_ns=?, size=?, sha256=?, indexed_at=?, n_chunks=? WHERE id=?",
            (title, mtime_ns, size, digest, now, len(chunks), file_id),
        )

    tag_str = " ".join(tags)
    conn.executemany(
        "INSERT INTO chunks(file_id,chunk_no,heading,text,topic,source,date,tags) VALUES (?,?,?,?,?,?,?,?)",
        [(file_id, i, c.heading, c.text, topic, source, date, tag_str) for i, c in enumerate(chunks)],
    )
    if tags and chunks:
        ids = [r[0] for r in conn.execute("SELECT id FROM chunks WHERE file_id=?", (file_id,))]
        conn.executemany("INSERT INTO chunk_tags(tag, chunk_id) VALUES (?,?)", [(t, i) for i in ids for t in tags])
    return len(chunks)


def sync(conn: sqlite3.Connection, notes_dir: Path, *, verify: bool = False, batch: int = 200) -> SyncStats:
    """Bring the index in line with notes_dir, touching only what changed.

    verify=True skips the mtime/size shortcut and hashes every file (still only re-chunks real changes).
    Commits every `batch` re-indexed files so a first build never holds the write lock for long.
    """
    t0 = time.perf_counter()
    notes_dir = Path(notes_dir).resolve()
    stats = SyncStats()
    disk = scan(notes_dir)
    known = {r["path"]: r for r in conn.execute("SELECT id,path,mtime_ns,size,sha256 FROM files")}

    pending = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for path in sorted(set(known) - set(disk)):
            conn.execute("DELETE FROM chunks WHERE file_id=?", (known[path]["id"],))
            conn.execute("DELETE FROM files WHERE id=?", (known[path]["id"],))
            stats.removed += 1
            pending += 1

        for path, (mtime_ns, size) in sorted(disk.items()):
            row = known.get(path)
            if row and not verify and row["sha256"] and row["mtime_ns"] == mtime_ns and row["size"] == size:
                stats.unchanged += 1
                continue
            try:
                raw = (notes_dir / path).read_bytes()
            except OSError:
                continue
            digest = hashlib.sha256(raw).hexdigest()
            if row and row["sha256"] == digest:
                conn.execute("UPDATE files SET mtime_ns=?, size=? WHERE id=?", (mtime_ns, size, row["id"]))
                stats.touched += 1
                continue
            stats.chunks_written += _index_file(conn, row["id"] if row else None, path, raw, mtime_ns, size, digest)
            if row:
                stats.updated += 1
            else:
                stats.added += 1
            pending += 1
            if pending >= batch:
                conn.execute("COMMIT")
                conn.execute("BEGIN IMMEDIATE")
                pending = 0
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise

    if stats.chunks_written >= 2000:  # big change: merge FTS segments for faster queries
        optimize(conn)
    stats.seconds = time.perf_counter() - t0
    return stats


def optimize(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('optimize')")
    conn.execute("PRAGMA optimize")


def rebuild(db_path: Path, notes_dir: Path) -> SyncStats:
    """Delete the index and build it from scratch."""
    db_path = Path(db_path)
    for suffix in ("", "-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    conn = connect(db_path)
    try:
        stats = sync(conn, notes_dir)
        optimize(conn)
        return stats
    finally:
        conn.close()


# --------------------------------------------------------------------------- search


def tokens(query: str) -> list[str]:
    """Lower-cased word tokens with stopwords removed (falls back to all words if that empties it)."""
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 1]
    return [w for w in words if w not in STOPWORDS] or words


def build_match(query: str) -> str | None:
    """Natural-language query -> FTS5 MATCH expression: OR of quoted terms, ranked by BM25."""
    toks = list(dict.fromkeys(tokens(query)))
    return " OR ".join(f'"{t}"' for t in toks) if toks else None


def search(
    conn: sqlite3.Connection,
    query: str = "",
    *,
    topic: str | None = None,
    source: str | None = None,
    tags: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """BM25-ranked chunk search with optional metadata filters.

    topic: exact (case-insensitive). source: prefix match. tags: chunk must have ALL of them.
    date_from / date_to: inclusive ISO dates. Empty query + filters = filter-only browse, newest first.
    """
    limit = max(1, min(int(limit), MAX_LIMIT))
    where: list[str] = []
    params: list = []
    if topic:
        where.append("c.topic = ?")
        params.append(topic)
    if source:
        escaped = source.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("c.source LIKE ? ESCAPE '\\'")
        params.append(escaped + "%")
    wanted = list(dict.fromkeys(t.strip().lstrip("#").lower() for t in (tags or []) if t.strip()))
    if wanted:
        marks = ",".join("?" * len(wanted))
        where.append(
            f"c.id IN (SELECT chunk_id FROM chunk_tags WHERE tag IN ({marks}) GROUP BY chunk_id HAVING COUNT(*) = ?)"
        )
        params.extend(wanted)
        params.append(len(wanted))
    if date_from:
        where.append("c.date >= ?")
        params.append(date_from)
    if date_to:
        where.append("c.date <= ?")
        params.append(date_to)

    match = build_match(query)
    if match:
        w1, w2, w3 = BM25_WEIGHTS
        sql = (
            "SELECT c.id, f.path, f.title, c.heading, c.topic, c.source, c.date, c.tags, "
            f"bm25(chunks_fts, {w1}, {w2}, {w3}) AS rank, "
            "snippet(chunks_fts, 1, '[', ']', '…', 24) AS snip "
            "FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid JOIN files f ON f.id = c.file_id "
            "WHERE chunks_fts MATCH ?" + "".join(f" AND {w}" for w in where) + " ORDER BY rank LIMIT ?"
        )
        rows = conn.execute(sql, [match, *params, limit]).fetchall()
    else:
        sql = (
            "SELECT c.id, f.path, f.title, c.heading, c.topic, c.source, c.date, c.tags, 0.0 AS rank, "
            "substr(c.text, 1, 200) AS snip "
            "FROM chunks c JOIN files f ON f.id = c.file_id"
            + (" WHERE " + " AND ".join(where) if where else "")
            + " ORDER BY c.date DESC, f.path, c.chunk_no LIMIT ?"
        )
        rows = conn.execute(sql, [*params, limit]).fetchall()

    return [
        {
            "id": r["id"],
            "path": r["path"],
            "name": r["path"].removesuffix(".md"),
            "title": r["title"],
            "heading": r["heading"],
            "topic": r["topic"],
            "source": r["source"],
            "date": r["date"],
            "tags": r["tags"].split(),
            "score": round(-r["rank"], 4) + 0.0,  # bm25() is lower-is-better (negative); flip so bigger = better
            "snippet": " ".join(r["snip"].split()),
        }
        for r in rows
    ]


def stats(conn: sqlite3.Connection, db_path: Path | None = None) -> dict:
    n_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    n_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    topics = {r[0]: r[1] for r in conn.execute("SELECT topic, COUNT(*) FROM chunks GROUP BY topic ORDER BY 2 DESC")}
    last = conn.execute("SELECT MAX(indexed_at) FROM files").fetchone()[0]
    size = os.path.getsize(db_path) if db_path and Path(db_path).exists() else None
    return {"files": n_files, "chunks": n_chunks, "topics": topics, "last_indexed": last, "db_bytes": size}
