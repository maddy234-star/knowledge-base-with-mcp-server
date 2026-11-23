#!/usr/bin/env python3
"""Hook: keep the search index current. Never blocks Claude (always exits 0).

- PostToolUse (Write|Edit|MultiEdit): if the edited file is a .md under the notes dir, sync the index.
- SessionStart: sync so a fresh session starts with an up-to-date index.
Sync is incremental, so this costs a few milliseconds when nothing changed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mcp-servers" / "knowledge-base"))

try:
    import index

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    notes = index.default_notes_dir()
    path = (payload.get("tool_input") or {}).get("file_path")
    if payload.get("hook_event_name") == "PostToolUse":
        if not path or not path.lower().endswith(".md"):
            sys.exit(0)
        try:
            Path(path).resolve().relative_to(notes)
        except ValueError:
            sys.exit(0)  # not a note
    conn = index.connect(index.default_db_path(notes))
    try:
        stats = index.sync(conn, notes)
    finally:
        conn.close()
    if stats.changed:
        print(f"knowledge-base index updated: {stats.summary()}", file=sys.stderr)
except Exception as exc:  # indexing problems must never break the session
    print(f"reindex hook skipped: {exc!r}", file=sys.stderr)
sys.exit(0)
