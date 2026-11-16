"""Prints the questions of the held-out test cases, and nothing else (no reference SQL, no answers).

    uv run python questions.py
"""
import json
from pathlib import Path

cases = [json.loads(line) for line in (Path(__file__).parent / "data" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
for c in cases:
    if c["split"] == "test":
        print("-", c["question"])
