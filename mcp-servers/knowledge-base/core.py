"""Note logic. No MCP imports, so it is easy to test and to swap out.

Search is backed by the SQLite FTS5 chunk index in `index.py` (BM25 ranking, metadata filters,
incremental sync). `search_notes` here collapses chunk hits to one hit per note, which is the shape
the evals use. Later courses (RAG / embeddings): swap the retrieval inside `index.search`.
"""
from pathlib import Path

import index


def _note_files(notes_dir: Path) -> list[Path]:
    return sorted(p for p in notes_dir.rglob("*.md") if p.is_file())


def _name(notes_dir: Path, path: Path) -> str:
    return path.relative_to(notes_dir).with_suffix("").as_posix()


def _title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem


def list_notes(notes_dir: Path) -> list[dict]:
    return [{"name": _name(notes_dir, p), "title": _title(p)} for p in _note_files(notes_dir)]


def get_note(notes_dir: Path, name: str) -> str | None:
    """Return a note's text, or None. Refuses anything outside notes_dir."""
    root = notes_dir.resolve()
    wanted = name.strip().removesuffix(".md").lower()
    for p in _note_files(notes_dir):
        if _name(notes_dir, p).lower() == wanted or p.stem.lower() == wanted:
            resolved = p.resolve()
            if resolved.is_relative_to(root):
                return resolved.read_text(encoding="utf-8")
    return None


def search_notes(notes_dir: Path, query: str, max_results: int = 5, **filters) -> list[dict]:
    """BM25 search over chunks, collapsed to the best chunk per note.

    `filters` are passed to index.search (topic, source, tags, date_from, date_to).
    Builds the index on first use; call index.sync() to pick up edits (the evals, server and watcher do).
    """
    conn = index.connect(index.default_db_path(notes_dir))
    try:
        if conn.execute("SELECT 1 FROM files LIMIT 1").fetchone() is None:
            index.sync(conn, notes_dir)
        hits = index.search(conn, query, limit=max(max_results * 5, 20), **filters)
    finally:
        conn.close()
    best: dict[str, dict] = {}
    for h in hits:  # already sorted best-first
        best.setdefault(h["name"], h)
    return [
        {"name": h["name"], "title": h["title"], "score": h["score"], "snippet": h["snippet"]}
        for h in list(best.values())[:max_results]
    ]
