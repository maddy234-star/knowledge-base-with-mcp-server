"""Score search quality. Run before and after every upgrade (e.g. switching to embeddings).

    python evals/run_eval.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-servers" / "knowledge-base"))
import core  # noqa: E402

NOTES = ROOT / "notes"
questions = json.loads((Path(__file__).parent / "questions.json").read_text())

top1 = top3 = 0
for q in questions:
    names = [h["name"] for h in core.search_notes(NOTES, q["question"], max_results=3)]
    hit1 = bool(names) and names[0] == q["expected"]
    hit3 = q["expected"] in names
    top1 += hit1
    top3 += hit3
    print(f"[{'PASS' if hit1 else 'FAIL'}] {q['question']}  ->  {names[:3]}")

n = len(questions)
print(f"\nTop-1: {top1}/{n}   Top-3: {top3}/{n}")
