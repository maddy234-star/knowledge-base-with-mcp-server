"""Personal knowledge-base MCP server (stdio transport).

Runs locally and only reads markdown files under NOTES_DIR. Search is backed by a SQLite FTS5
chunk index (BM25 + metadata filters) kept in step with the notes by incremental sync.
IMPORTANT: never print() to stdout in a stdio server; it corrupts the protocol.
Use logging (stderr) instead.
"""
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent))
import core  # noqa: E402
import index  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
log = logging.getLogger("knowledge-base")

NOTES_DIR = index.default_notes_dir()
DB_PATH = index.default_db_path(NOTES_DIR)

mcp = FastMCP("knowledge-base")


@contextmanager
def _db():
    conn = index.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _startup_sync() -> None:
    try:
        with _db() as conn:
            log.info("index sync: %s", index.sync(conn, NOTES_DIR).summary())
    except Exception:  # never stop the server because indexing failed
        log.exception("startup index sync failed")


@mcp.tool()
def list_notes() -> str:
    """List every note in the knowledge base with its name and title."""
    notes = core.list_notes(NOTES_DIR)
    if not notes:
        return "No notes found."
    return "\n".join(f"- {n['name']}: {n['title']}" for n in notes)


@mcp.tool()
def search_notes(
    query: str = "",
    max_results: int = 5,
    topic: str = "",
    source: str = "",
    tags: str = "",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """BM25 search over chunks of my personal learning notes. Returns the best matching sections
    (note > heading), with score, topic, date, tags and a snippet. Use get_note to read a full note.

    Optional filters, combinable with the query or used alone (then newest first):
    topic (exact), source (prefix), tags (comma-separated, chunk must have all),
    date_from / date_to (inclusive, YYYY-MM-DD)."""
    tag_list = [t for t in tags.split(",") if t.strip()]
    with _db() as conn:
        hits = index.search(
            conn, query, topic=topic or None, source=source or None, tags=tag_list or None,
            date_from=date_from or None, date_to=date_to or None, limit=max_results,
        )
    if not hits:
        return f"No notes matched '{query}' with those filters."
    return "\n".join(
        f"- {h['name']} > {h['heading']} (score {h['score']}, topic {h['topic']}, {h['date']}, "
        f"tags {','.join(h['tags']) or '-'}): {h['snippet']}"
        for h in hits
    )


@mcp.tool()
def get_note(name: str) -> str:
    """Return the full text of one note. `name` is as shown by list_notes or search_notes."""
    text = core.get_note(NOTES_DIR, name)
    return text if text is not None else f"No note named '{name}'. Try list_notes."


@mcp.tool()
def reindex(verify: bool = False) -> str:
    """Bring the search index up to date with the notes folder. Incremental: only added, changed or
    deleted notes are re-chunked. Set verify=true to re-hash every file instead of trusting mtime."""
    with _db() as conn:
        return index.sync(conn, NOTES_DIR, verify=verify).summary()


@mcp.tool()
def index_stats() -> str:
    """Show how many notes and chunks are indexed, per-topic counts and when it was last updated."""
    with _db() as conn:
        s = index.stats(conn, DB_PATH)
    topics = ", ".join(f"{t}: {n}" for t, n in s["topics"].items()) or "none"
    return f"{s['files']} notes, {s['chunks']} chunks, last indexed {s['last_indexed']}. Topics: {topics}"


if __name__ == "__main__":
    _startup_sync()
    mcp.run()  # stdio by default
