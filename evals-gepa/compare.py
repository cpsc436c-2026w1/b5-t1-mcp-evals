"""Step 9: the before/after comparison on the held-out (test) cases, and the cost of the whole run in CAD.
No model calls: it reads the Inspect logs in logs/ and logs/optimize.log.

    uv run python compare.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGS = HERE / "logs"


def eval_runs() -> list[dict]:
    from inspect_ai.log import list_eval_logs, read_eval_log

    runs = []
    for info in list_eval_logs(str(LOGS)):
        log = read_eval_log(info, header_only=True)
        if log.status != "success" or not log.results:
            continue
        m = {s.name: {k: v.value for k, v in s.metrics.items()} for s in log.results.scores}
        meta = log.eval.metadata or {}
        runs.append(dict(when=log.eval.created, split=meta.get("split"), prompt=meta.get("prompt"),
                         n=log.results.completed_samples, score=m.get("sql_check", {}).get("accuracy"),
                         cost=m.get("cost_cad", {}).get("total", 0.0)))
    return sorted(runs, key=lambda r: r["when"])


def optimize_cost() -> float:
    p = LOGS / "optimize.log"
    return sum(float(x) for x in re.findall(r"^cost ([\d.]+) CAD", p.read_text(encoding="utf-8"), re.M)) if p.exists() else 0.0


def main() -> int:
    runs = eval_runs()
    print(f"{'when':<26} {'split':<6} {'prompt':<22} {'cases':>5} {'score':>6} {'cost CAD':>10}")
    for r in runs:
        print(f"{r['when'][:25]:<26} {r['split']!s:<6} {r['prompt']!s:<22} {r['n']:>5} {r['score']:>6.3f} {r['cost']:>10.6f}")
    test = {r["prompt"]: r for r in runs if r["split"] == "test"}  # the latest run of each prompt
    opt = optimize_cost()
    total = sum(r["cost"] for r in runs) + opt
    print(f"GEPA (logs/optimize.log): {opt:.6f} CAD")
    print(f"cost of everything in logs/: {total:.6f} CAD")
    before, after = test.get("prompt.txt"), test.get("prompt.optimized.txt")
    if not (before and after):
        print("For the comparison, run the test split with prompt.txt and with prompt.optimized.txt (steps 4 and 8).")
        return 1
    ok = after["score"] >= before["score"]
    print(f"held-out cases: before {before['score']:.3f}, after {after['score']:.3f}")
    print("check: the after score is at least the before score on the held-out cases: " + ("yes" if ok else "NO"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
