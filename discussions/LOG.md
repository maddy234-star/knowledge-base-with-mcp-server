# Discussion log

Newest entries at the bottom. One dated section per working session. Append only.

## 2026-11-22
- Earlier conversation (Oct 10, project creation) was not recoverable: no transcript was saved. The user searched for
  it via `/resume`; likely it happened outside Claude Code.
- Reviewed all files and summarised the project.
- Created venv with native arm64 Python (the shell runs under Rosetta; the x86_64 build failed on `cryptography`).
- Added `.mcp.json`; verified the server over stdio (3 tools) and ran evals: 7/7 top-1, 7/7 top-3.
- Fixed loose ends: README path (`cd knowledge-base-with-mcp-server`), PyDev Python 3.8 -> 3.14, added a Stop hook
  (`.claude/hooks/check_evals.py`, blocks once if evals fail; tested pass, fail and loop-guard cases).
- `git init` on `main`, initial commit `bd74aa3`, without a co-author line at the user's request. Added `.DS_Store` to `.gitignore`.
- Explained how to connect GitHub (add remote, `gh auth login`, push). Waiting for the repo URL.
- Added `discussions/` (this folder) and `/save-discussion` so context persists across sessions.
- Built the SQLite FTS5 index (`index.py`): chunk-level BM25, metadata columns (topic/source/date/tags) with B-tree
  indexes, external-content FTS table + triggers, WAL. Incremental `sync()` by mtime+size then sha256; touched-but-
  identical files are not re-chunked; deletions handled; `CHUNKER_VERSION` forces re-chunk when rules change.
- Added `kb_index.py` CLI (sync, sync --verify, rebuild, search, stats, watch), MCP tools `reindex`/`index_stats`,
  search filters on `search_notes`, front matter on the three starter notes, `tests/test_index.py` (14 tests).
- Indexing agent: `watch` poller (tested: add/edit/delete picked up in ~1 s), `.claude/hooks/reindex.py` wired to
  SessionStart and PostToolUse, and the `kb-indexer` subagent.
- Benchmark (50k synthetic chunks): build 7.7 s, no-change sync 13 ms, one-file sync ~15 ms, content-word query
  0.6 ms p50, worst-case common-word query 20-40 ms. Evals still 7/7. Not committed.
