# AI Learning Lab

A personal knowledge-base MCP server for Claude Code, built as a project for the "Claude Code in Action"
course and designed to grow with later courses.

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
| Embeddings / RAG | Replace the body of `search_notes` in `core.py` with vector search. Same signature, same tools. |
| Agents / subagents | Add `.claude/agents/study-planner.md` that reads notes and proposes what to study next. |
| Evals | Grow `evals/questions.json` and compare scores before and after each change. |
| Any new course | Add `modules/NN-name/` and a section in `LEARNINGS.md`. |
