# Project state (auto-loaded every session via CLAUDE.md)

Keep this file short and current. Update it with `/save-discussion`. Full history is in `discussions/LOG.md`.

## What this is
Personal knowledge-base MCP server ("AI Learning Lab") for the "Claude Code in Action" course. Notes in `notes/`
are exposed to Claude Code via a stdio MCP server (`list_notes`, `search_notes` with filters, `get_note`, `reindex`, `index_stats`).

## Current status (as of 2026-11-22)
- Server, evals (7/7 top-1 and top-3), `/learned` command and Stop hook (runs evals) are working and tested.
- `.mcp.json` launches `arch -arm64 .venv/bin/python mcp-servers/knowledge-base/server.py`.
- Search is a SQLite FTS5 chunk index (`index.py`, BM25, metadata columns topic/source/date/tags, incremental sync by
  mtime+size then sha256). 14 unit tests pass; evals 7/7. Benchmarked at 50k chunks: see README.
- Index freshness: `kb_index.py watch` daemon, SessionStart + PostToolUse hooks, `reindex` tool, `kb-indexer` subagent.
- Git repo initialised on `main`, one commit; the index work is NOT committed yet. No remote yet: the user has a GitHub repo and will share the URL.

## Decisions
- MCP SDK pinned to 1.x (`mcp[cli]>=1.2,<2`); 2.x renamed FastMCP.
- Search logic stays in `core.py` (no MCP imports) so it can be tested and swapped for embeddings later.
- Venv must be arm64: the shell runs under Rosetta (x86_64) but installed wheels are arm64, hence `arch -arm64`.
- Commits in this repo: NO Co-Authored-By line (user preference).
- Index is generated (`.kb/`, gitignored); chunking rules are versioned by `CHUNKER_VERSION`.
- Watcher uses polling (stdlib only, no watchdog dependency); cheap because unchanged files cost one stat().
- Worst-case latency is all-common-word queries (20-40 ms at 50k chunks); typical content queries ~1 ms.
- Personal learning only: no work content in notes.

## Open items
- Push to the user's GitHub repo once the URL is provided (do not force-push; confirm before pushing).
- Replace the 3 starter notes in `notes/` with the user's own notes.
- Fill in `LEARNINGS.md` (use `/learned <topic>`).
- Verify the server shows as connected via `/mcp` in a fresh `claude` session.
- Commit the index work (user must ask). Decide whether to run `watch` at login (launchd) - not installed.
- Future: embeddings/RAG search (hybrid with BM25), dropping very common query terms to speed worst case, a study-planner subagent, more eval questions.
- `src/testServer.ts` is an unrelated TypeScript demo MCP server (`add_numbers`).
