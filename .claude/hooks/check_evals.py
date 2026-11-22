#!/usr/bin/env python3
"""Stop hook: run the search evals; if they fail, block the stop once so Claude fixes them.

Exit 0 = allow stop. Exit 2 = block stop (stderr is fed back to Claude).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    payload = {}

if payload.get("stop_hook_active"):  # already blocked once; avoid an infinite loop
    sys.exit(0)

result = subprocess.run(
    [sys.executable, str(ROOT / "evals" / "run_eval.py")], capture_output=True, text=True, cwd=ROOT
)
if result.returncode != 0 or "FAIL" in result.stdout:
    print("Search evals are failing. Fix before finishing:\n" + result.stdout + result.stderr, file=sys.stderr)
    sys.exit(2)
sys.exit(0)
