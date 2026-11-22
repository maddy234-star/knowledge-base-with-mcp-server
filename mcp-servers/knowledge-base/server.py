"""Personal knowledge-base MCP server (stdio transport).

Runs locally and only reads markdown files under NOTES_DIR.
IMPORTANT: never print() to stdout in a stdio server; it corrupts the protocol.
Use logging (stderr) instead.
"""
import logging
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent))
import core  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

DEFAULT_NOTES = Path(__file__).resolve().parents[2] / "notes"
NOTES_DIR = Path(os.environ.get("KB_NOTES_DIR", DEFAULT_NOTES)).expanduser().resolve()

mcp = FastMCP("knowledge-base")


@mcp.tool()
def list_notes() -> str:
    """List every note in the knowledge base with its name and title."""
    notes = core.list_notes(NOTES_DIR)
    if not notes:
        return "No notes found."
    return "\n".join(f"- {n['name']}: {n['title']}" for n in notes)


@mcp.tool()
def search_notes(query: str, max_results: int = 5) -> str:
    """Keyword-search my personal learning notes. Returns note names, scores and a matching line.
    Use get_note afterwards to read a full note."""
    hits = core.search_notes(NOTES_DIR, query, max_results)
    if not hits:
        return f"No notes matched '{query}'."
    return "\n".join(f"- {h['name']} (score {h['score']}): {h['snippet']}" for h in hits)


@mcp.tool()
def get_note(name: str) -> str:
    """Return the full text of one note. `name` is as shown by list_notes or search_notes."""
    text = core.get_note(NOTES_DIR, name)
    return text if text is not None else f"No note named '{name}'. Try list_notes."


if __name__ == "__main__":
    mcp.run()  # stdio by default
