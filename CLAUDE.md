# AI Learning Lab

Personal repo for applying what I learn in AI courses. Each course adds a module. Personal learning
only: use my own notes and sample data, nothing from work.

## Layout
- `notes/`: my learning notes (markdown). This is the knowledge base.
- `mcp-servers/knowledge-base/`: MCP server exposing the notes (`core.py` = logic, `server.py` = MCP wrapper).
- `modules/NN-course-name/`: work for each course.
- `evals/`: questions with known answers to measure search quality.
- `LEARNINGS.md`: one section per course.

## Using my notes
- For any question about what I have learned or my course notes, call the `knowledge-base` MCP tools first
  (`search_notes`, then `get_note`) before answering from general knowledge.
- Say which notes you used. If nothing matches, say so instead of guessing.

## Conventions
- Python 3.10+, type hints, small functions.
- The MCP server is stdio: never `print()` to stdout in `server.py`; log to stderr.
- Keep search logic in `core.py` so it can be tested without MCP.
- After changing search behaviour, run `python evals/run_eval.py` and report the scores.

## Commands
- Run evals: `python evals/run_eval.py`
- Check the server is connected: `/mcp`
