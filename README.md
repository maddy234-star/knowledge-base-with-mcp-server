# AI Learning Lab

Built a knowledge base with MCP server to gain an understanding of framework, evals, agents etc.

A personal knowledge-base MCP server for Claude Code, built as a project for the "Claude Code in Action"
course and designed to grow with later courses.

> How it fits together: see [ARCHITECTURE.md](ARCHITECTURE.md).

## Quick start

```bash
cd knowledge-base-with-mcp-server
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
# Apple Silicon Mac whose shell runs under Rosetta? Create the venv with: arch -arm64 python3 -m venv .venv
pip install -r mcp-servers/knowledge-base/requirements.txt
python evals/run_eval.py                                  # sanity check, no MCP needed
```

Install Claude Code (see Anthropic's docs for current instructions), then from the repo root:

```bash
claude
```

The repo includes `.mcp.json`, so Claude Code will offer to enable the `knowledge-base` server. Approve it,
then run `/mcp` to confirm it is connected. Try:

- `/learned MCP servers`
- "What did I learn about hooks?"

**Using a virtualenv?** `.mcp.json` already points at `.venv/bin/python`, launched through `arch -arm64`
(macOS Apple Silicon). On Linux/Windows or an Intel Mac, edit it to `"command": ".venv/bin/python"`
(Windows: `.venv\Scripts\python.exe`) and drop the `arch` / `-arm64` entries. Alternatively register it yourself:
`claude mcp add knowledge-base -- /full/path/to/.venv/bin/python mcp-servers/knowledge-base/server.py`

**Using Eclipse?** Open a terminal inside Eclipse (or any external terminal) at the repo root and run `claude`.
Everything here lives in the repo, so it works with or without an IDE plugin.

## Stop hook
`.claude/settings.json` runs `.claude/hooks/check_evals.py` when Claude finishes a turn. If the evals fail, it
blocks the stop once and tells Claude to fix the search. Remove the `hooks` block to disable it.

## Search index (SQLite FTS5 + BM25)
Search runs over **chunks** (sections of notes, at most 900 characters), not whole files, using an SQLite FTS5
index in `.kb/index.db` (generated, gitignored). Ranking is BM25 with heading and tag matches weighted higher.

**Metadata filters.** Put optional front matter at the top of a note; it is stored in real columns, so filters run in
SQL alongside the text query:

```markdown
---
topic: mcp
source: Claude Code in Action course
date: 2026-10-10
tags: [mcp, stdio]
---
```

Defaults: topic = first sub-folder under `notes/` (else `general`), source = file path, date = file modified date.
`search_notes` accepts `topic` (exact), `source` (prefix), `tags` (comma-separated, all must match), `date_from`,
`date_to`; with no query it browses by filter, newest first.

**Incremental indexing.** Each file's mtime, size and sha256 are stored. A sync skips unchanged files after one
`stat()`, refreshes only the mtime of touched-but-identical files, and re-chunks only files whose content changed.
Deleted notes are removed. A full rebuild is never needed in normal use.

```bash
python3 mcp-servers/knowledge-base/kb_index.py sync      # incremental
python3 mcp-servers/knowledge-base/kb_index.py sync --verify   # re-hash everything, re-chunk only real changes
python3 mcp-servers/knowledge-base/kb_index.py rebuild   # from scratch (rarely needed)
python3 mcp-servers/knowledge-base/kb_index.py search "stdio" --topic mcp --tag stdio --from 2026-01-01
python3 mcp-servers/knowledge-base/kb_index.py stats
```

**Keeping it fresh (the indexing agent).** Four layers, all incremental, so overlap is harmless:
1. `kb_index.py watch` is the background agent: it polls `notes/` every 2 s and re-indexes on any add, edit or
   delete, from any editor. Run it in a spare terminal: `python3 mcp-servers/knowledge-base/kb_index.py watch`
   (or in the background: `nohup python3 mcp-servers/knowledge-base/kb_index.py watch > .kb/watch.log 2>&1 &`).
2. Claude Code hooks (`.claude/settings.json`): `SessionStart` syncs when a session opens; `PostToolUse` syncs after
   Claude writes or edits a note.
3. The MCP server syncs at startup and exposes a `reindex` tool.
4. The `kb-indexer` subagent (`.claude/agents/kb-indexer.md`) can be invoked by Claude to sync, verify or rebuild.

**Measured on this laptop** (`python3 evals/bench_index.py`, 50,000 chunks, 114 MB index): initial build 7.7 s;
no-change sync of 2,000 files 13 ms; one edited or added file about 15 ms; content-word queries 0.6 ms p50 /
1.5 ms p95 (0.3 ms with a topic filter); filter-only 1.5 ms. Worst case, queries made only of words that appear in
most chunks, takes 20-40 ms because BM25 must score every match.

## Notes
The three files in `notes/` are generic starters. Replace them with your own notes. Any `.md` file under
`notes/` (including subfolders) is picked up automatically. Point the server elsewhere with the
`KB_NOTES_DIR` environment variable.

## Why the MCP SDK is pinned to 1.x
The `mcp` Python package's 2.x release renamed `FastMCP` and changed other APIs. This project uses the 1.x
API (`from mcp.server.fastmcp import FastMCP`), which most tutorials use. Migrate deliberately later.

## Privacy
The server runs locally over stdio and only reads the notes folder. Nothing is sent anywhere by this code.
Claude Code itself sends your conversation, including any note content Claude reads, to Anthropic, so keep
notes to personal learning material.

## Extending with future courses
| Course topic | Change |
|---|---|
| Embeddings / RAG | Add vector retrieval next to `index.search` (same chunks, same metadata filters); fuse with BM25 scores. |
| Agents / subagents | Add `.claude/agents/study-planner.md` that reads notes and proposes what to study next. |
| Evals | Grow `evals/questions.json` and compare scores before and after each change. |
| Any new course | Add `modules/NN-name/` and a section in `LEARNINGS.md`. |
