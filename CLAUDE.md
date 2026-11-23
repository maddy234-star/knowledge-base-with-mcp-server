# AI Learning Lab

Personal repo for applying what I learn in AI courses. Each course adds a module. Personal learning
only: use my own notes and sample data, nothing from work.

## Project memory
@discussions/STATE.md

- Full history: `discussions/LOG.md` (read it when you need detail on past decisions).
- At the end of a working session, the user runs `/save-discussion` to update both files.

## Layout
- `notes/`: my learning notes (markdown). This is the knowledge base.
- `mcp-servers/knowledge-base/`: MCP server exposing the notes. `index.py` = SQLite FTS5 chunk index (BM25, filters,
  incremental sync), `core.py` = note logic, `server.py` = MCP wrapper, `kb_index.py` = CLI (sync/rebuild/watch/search/stats).
- `ARCHITECTURE.md`: diagrams and design of the whole server. Read it before structural changes.
- `tests/`: unit tests for the index. `.kb/index.db` is the generated index (gitignored).
- `modules/NN-course-name/`: work for each course.
- `evals/`: questions with known answers to measure search quality.
- `LEARNINGS.md`: one section per course.
- `discussions/`: `STATE.md` (current status, auto-loaded) and `LOG.md` (dated history).

## Using my notes
- For any question about what I have learned or my course notes, call the `knowledge-base` MCP tools first
  (`search_notes`, then `get_note`) before answering from general knowledge.
- Say which notes you used. If nothing matches, say so instead of guessing.

## Conventions
- Python 3.10+, type hints, small functions.
- The MCP server is stdio: never `print()` to stdout in `server.py`; log to stderr.
- Keep search/index logic in `index.py` / `core.py` (no MCP imports) so it can be tested without MCP.
- Note metadata is optional front matter (`topic`, `source`, `date`, `tags`); see the `index.py` docstring.
- Indexing is incremental (mtime+size, then sha256). Bump `CHUNKER_VERSION` in `index.py` when chunking rules change.
- After editing notes, the index is refreshed by hooks, the `watch` agent or the `kb-indexer` subagent; or run `reindex`.
- After changing search or indexing behaviour, run `python3 evals/run_eval.py` and `python3 -m unittest discover -s tests`, and report the results.

## Commands
- Run evals: `python3 evals/run_eval.py`  |  Unit tests: `python3 -m unittest discover -s tests`
- Index: `python3 mcp-servers/knowledge-base/kb_index.py sync|rebuild|watch|search|stats`
- Benchmark (synthetic 50k chunks): `python3 evals/bench_index.py`
- Check the server is connected: `/mcp`
