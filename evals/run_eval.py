"""Score search quality. Run before and after every upgrade (e.g. switching to embeddings).

    python evals/run_eval.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-servers" / "knowledge-base"))
import core  # noqa: E402
import index  # noqa: E402

NOTES = ROOT / "notes"
_conn = index.connect(index.default_db_path(NOTES))
print("index sync:", index.sync(_conn, NOTES).summary())  # make sure the index matches the notes
_conn.close()
questions = json.loads((Path(__file__).parent / "questions.json").read_text())

top1 = top3 = 0
for q in questions:
    names = [h["name"] for h in core.search_notes(NOTES, q["question"], max_results=3, **q.get("filters", {}))]
    if q["expected"] is None:  # nothing should match (out of scope, or excluded by the filters)
        hit1 = hit3 = not names
    else:
        hit1 = bool(names) and names[0] == q["expected"]
        hit3 = q["expected"] in names
    top1 += hit1
    top3 += hit3
    flt = f" {q['filters']}" if q.get("filters") else ""
    print(f"[{'PASS' if hit1 else 'FAIL'}] {q['question']}{flt}  ->  {names[:3]}")

n = len(questions)
print(f"\nTop-1: {top1}/{n}   Top-3: {top3}/{n}")
