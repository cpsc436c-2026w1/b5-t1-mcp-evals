"""Sizing of one student run, printed before any call is made. The arithmetic is in REPORT.md as well.

    uv run python budget.py
"""

from __future__ import annotations

import math
from pathlib import Path

import gateway
import scoring

HERE = Path(__file__).resolve().parent

MAX_METRIC_CALLS = 40      # GEPA's budget of worker calls on train and val cases
MINIBATCH = 3              # cases per GEPA reflection step
OPTIMIZE_BUDGET_CAD = 0.05 # the cost meter in optimize.py stops GEPA here
RUN_LIMIT_CAD = 0.10       # the course rule for one whole run
RATE_PER_MIN = 120         # requests a minute per student key
WORKER_S, REFLECT_S = 10, 45   # slow-case seconds per call (1024 or 4096 tokens at ~100 tokens/s)
REFLECT_TEMPLATE_CHARS = 1800   # GEPA's reflection instructions, without the prompt and the examples
FEEDBACK_CHARS = 700            # one case in the reflection prompt: question, reply, feedback


def estimate(prompt_text: str | None = None) -> dict:
    """Upper bounds for the models chosen now (TASK_MODEL, GEPA_REFLECTOR). A model outside the course price list
    counts as 0 CAD; `unknown` lists those models."""
    worker, refl = gateway.task_model(), gateway.reflector()
    prompt_text = prompt_text or (HERE / "prompt.txt").read_text(encoding="utf-8")
    n = {s: len(scoring.cases(s)) for s in ("train", "val", "test")}
    p_chars = 2 * len(prompt_text) + 200     # the prompt may double in length during GEPA
    w_in = p_chars // 3 + 30                 # tokens; 3 characters a token is on the high side
    r_in = (REFLECT_TEMPLATE_CHARS + p_chars + MINIBATCH * FEEDBACK_CHARS) // 3
    # GEPA checks its budget before an iteration, so the last one can go over by 2 minibatches and one val pass.
    gepa_worker = MAX_METRIC_CALLS + 2 * MINIBATCH + n["val"]
    # Every reflection costs at least 2 minibatches; the first val pass comes before any reflection.
    reflections = math.floor((gepa_worker - n["val"]) / (2 * MINIBATCH))
    calls = dict(check=1, eval_before=n["test"], gepa_worker=gepa_worker, gepa_reflect=reflections,
                 eval_after=n["test"])
    cost = dict(check=gateway.cad(worker, 40, 200),
                eval_before=n["test"] * gateway.cad(worker, w_in, gateway.WORKER_MAX_TOKENS),
                gepa_worker=gepa_worker * gateway.cad(worker, w_in, gateway.WORKER_MAX_TOKENS),
                gepa_reflect=reflections * gateway.cad(refl, r_in, gateway.REFLECTOR_MAX_TOKENS))
    cost["eval_after"] = cost["eval_before"]
    # Slowest GEPA: i iterations, k of them better on the minibatch (those add a val pass); worker calls bound it.
    wave = lambda k: math.ceil(k / gateway.CONCURRENCY) * WORKER_S  # noqa: E731
    gepa_s = max(wave(n["val"]) + i * (2 * wave(MINIBATCH) + REFLECT_S) + k * wave(n["val"])
                 for i in range(reflections + 1) for k in range(i + 1)
                 if n["val"] + 2 * MINIBATCH * i + n["val"] * k <= gepa_worker)
    secs = WORKER_S + 2 * wave(n["test"]) + gepa_s
    return dict(cases=n, calls=calls, total_calls=sum(calls.values()), cost_cad=cost,
                total_cad=sum(cost.values()), worst_seconds=secs, tokens=dict(worker_in=w_in, reflect_in=r_in),
                models=dict(task=worker, reflect=refl),
                unknown=[m for m in dict.fromkeys((worker, refl)) if not gateway.price_known(m)])


def print_estimate(e: dict | None = None) -> dict:
    e = e or estimate()
    print("Estimate for one whole run (check, eval, GEPA, eval again), before any call is made:")
    print(f"  models: task {e['models']['task']}, reflection {e['models']['reflect']}")
    for m in e["unknown"]:
        print(f"  cost unknown for {m}: not a course gateway price; its calls count as 0 CAD below")
    print(f"  cases: train {e['cases']['train']}, val {e['cases']['val']}, test (held out) {e['cases']['test']}")
    for k, v in e["calls"].items():
        print(f"  {k:<13} at most {v:>3} calls, at most {e['cost_cad'].get(k, 0):.4f} CAD")
    print(f"  total         at most {e['total_calls']:>3} calls, at most {e['total_cad']:.4f} CAD "
          f"(limit {RUN_LIMIT_CAD:.2f} CAD))
    print(f"  {e['total_calls']} calls in the whole run (plus retries) is fewer than the {RATE_PER_MIN} a minute a key may make.")
    return e


if __name__ == "__main__":
    print_estimate()
