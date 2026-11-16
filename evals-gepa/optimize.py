"""Step 6: dspy.GEPA rewrites the prompt, using the train and val cases only. The test cases are never loaded here.

    uv run python optimize.py                      # reads prompt.txt, writes prompt.optimized.txt
    uv run python optimize.py --max-metric-calls 12 --budget-cad 0.01

The DSPy program is one dspy.Predict("question -> sql") whose instructions are the text of prompt.txt.
Two small pieces keep it the same as the eval:
  - PlainSQL, a DSPy adapter: it sends the instructions as the system message and the question as the user
    message, and reads the whole reply as the SQL. So the prompt GEPA rewrites is the exact system prompt that
    task.py sends. (DSPy's default adapter would wrap it in its own field format.)
  - GatewayLM, a DSPy LM whose engine calls gateway.chat(), so every call goes through the cost meter, the retries
    and the plain error messages.
Worker model answers the cases; reflection model reads the failures and writes a new prompt.
Writes prompt.optimized.txt and logs/optimize.log."""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path

import dspy
from dspy.adapters.base import Prompt, user_message
from dspy.lm15 import Message, Response, TextPart, Usage, response_to_events

import budget
import gateway
import scoring

HERE = Path(__file__).resolve().parent


def short(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:8]


def _text(parts) -> str:
    return parts if isinstance(parts, str) else "".join(p.text for p in parts if isinstance(p, TextPart))


class GatewayEngine:
    """DSPy engine: one gateway.chat() call per DSPy request."""

    def __init__(self, model: str, max_tokens: int, meter: gateway.Meter, role: str):
        self.model, self.max_tokens, self.meter, self.role = model, max_tokens, meter, role

    def complete(self, request):
        msgs = [{"role": "system", "content": _text(request.system)}] if request.system else []
        msgs += [{"role": m.role, "content": _text(m.parts)} for m in request.messages]
        # DSPy turns an error inside an LM call into a score of 0 for that case and goes on. So the first
        # budget or gateway error is kept on the meter, every later call is refused, and AbortOnError stops GEPA.
        if self.meter.abort is not None:
            raise RuntimeError(f"refused: {self.meter.abort}")
        try:
            r = gateway.chat(self.model, msgs, self.max_tokens, self.meter, role=self.role)
        except (gateway.BudgetExceeded, gateway.GatewayError) as ex:
            self.meter.abort = self.meter.abort or ex
            raise RuntimeError(str(ex)) from None
        return Response(id=None, model=self.model, message=Message.assistant([TextPart(r["text"])]),
                        finish_reason="stop", usage=Usage(input_tokens=r["tokens_in"], output_tokens=r["tokens_out"],
                                                          total_tokens=r["tokens_in"] + r["tokens_out"]))

    def stream(self, request):
        return response_to_events(self.complete(request))

    def close(self):
        pass


class GatewayLM(dspy.BaseLM):
    def __init__(self, model: str, max_tokens: int, meter: gateway.Meter, role: str):
        super().__init__(model=model, cache=False, temperature=0, max_tokens=max_tokens, num_retries=0,
                         engine=GatewayEngine(model, max_tokens, meter, role))


class PlainSQL(dspy.Adapter):
    """System message = the instructions (the prompt file), user message = the question, reply = the SQL."""

    def format(self, signature, demos, inputs):
        return Prompt(messages=[user_message(inputs["question"])], system=signature.instructions)

    def parse(self, signature, completion):
        return {"sql": completion}


class SqlProgram(dspy.Module):
    """One predictor. Only its calls use PlainSQL; GEPA's own reflection calls keep DSPy's adapters."""

    def __init__(self, instructions: str):
        super().__init__()
        self.predict = dspy.Predict(dspy.Signature("question -> sql", instructions))

    def forward(self, question):
        with dspy.context(adapter=PlainSQL()):
            return self.predict(question=question)


def metric(gold, pred, trace=None, pred_name=None, pred_trace=None, program_trace=None):
    score, kind, feedback = scoring.check(pred.sql or "", dict(gold))
    return dspy.Prediction(score=score, feedback=feedback)


class StopBeforeBudget:
    """Stops GEPA between iterations when one more iteration could pass the budget."""

    def __init__(self, meter: gateway.Meter, prompt: str):
        e = budget.estimate(prompt)
        per_worker = e["cost_cad"]["gepa_worker"] / max(e["calls"]["gepa_worker"], 1)
        per_reflect = e["cost_cad"]["gepa_reflect"] / max(e["calls"]["gepa_reflect"], 1)
        self.meter = meter
        self.reserve = (2 * budget.MINIBATCH + e["cases"]["val"]) * per_worker + per_reflect

    def __call__(self, state) -> bool:
        return self.meter.spent + self.reserve > self.meter.budget


class AbortOnError:
    def __init__(self, meter: gateway.Meter):
        self.meter = meter

    def __call__(self, state) -> bool:
        return self.meter.abort is not None


class BestOnVal:
    """Remembers the best prompt on a full val pass, to write it if the cost meter stops the run."""

    def __init__(self):
        self.best = (-1.0, "")

    def __call__(self, state) -> bool:
        for prog, s in zip(state.program_candidates, state.program_full_scores_val_set):
            if s > self.best[0]:
                self.best = (s, next(iter(prog.values())))
        return False


def examples(split: str) -> list:
    return [dspy.Example(**c).with_inputs("question") for c in scoring.cases(split)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="prompt.txt")
    ap.add_argument("--out", default="prompt.optimized.txt")
    ap.add_argument("--max-metric-calls", type=int, default=budget.MAX_METRIC_CALLS)
    ap.add_argument("--budget-cad", type=float, default=budget.OPTIMIZE_BUDGET_CAD)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    seed_prompt = (HERE / a.prompt).read_text(encoding="utf-8")
    train, val = examples("train"), examples("val")
    e = budget.estimate(seed_prompt)
    print(f"dspy.GEPA: train {len(train)} cases, val {len(val)} cases, at most {a.max_metric_calls} worker calls "
          f"(+ one last iteration), cost meter stops at {a.budget_cad:.4f} CAD.")
    print(f"estimate: at most {e['calls']['gepa_worker']} worker and {e['calls']['gepa_reflect']} reflection calls, "
          f"at most {e['cost_cad']['gepa_worker'] + e['cost_cad']['gepa_reflect']:.4f} CAD.")
    try:
        gateway.token()  # a plain message now if the token is not set
    except gateway.GatewayError as ex:
        print(f"PROBLEM: {ex}")
        return 1
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("dspy.teleprompt.gepa").setLevel(logging.INFO)  # one line per GEPA step, with each new prompt
    meter = gateway.Meter(a.budget_cad)
    worker = GatewayLM(gateway.WORKER, gateway.WORKER_MAX_TOKENS, meter, "worker")
    reflector = GatewayLM(gateway.REFLECTOR, gateway.REFLECTOR_MAX_TOKENS, meter, "reflect")
    program = SqlProgram(seed_prompt)
    best_seen = BestOnVal()
    gepa = dspy.GEPA(metric=metric, max_metric_calls=a.max_metric_calls, reflection_lm=reflector,
                     reflection_minibatch_size=budget.MINIBATCH, candidate_selection_strategy="pareto",
                     use_merge=False, num_threads=gateway.CONCURRENCY, track_stats=True, seed=a.seed,
                     gepa_kwargs={"stop_callbacks": [best_seen, AbortOnError(meter), StopBeforeBudget(meter, seed_prompt)]})
    t0, stopped, result = time.time(), None, None
    try:
        with dspy.context(lm=worker):
            result = gepa.compile(program, trainset=train, valset=val)
    except Exception:  # noqa: BLE001  the cause is on the meter; anything else is re-raised below
        if meter.abort is None:
            raise
    ex = meter.abort
    if isinstance(ex, gateway.BudgetExceeded):
        stopped, result = str(ex), None
    elif ex is not None:
        print(f"PROBLEM: {ex}")
        print(f"GEPA stopped. It had cost {meter.spent:.6f} CAD. Nothing was written. Run this step again.")
        (HERE / "logs").mkdir(exist_ok=True)
        with (HERE / "logs" / "optimize.log").open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\nstopped: {ex}\ncost {meter.spent:.6f} CAD\n\n")
        return 1

    if result is not None:
        best = result.predict.signature.instructions
        d = result.detailed_results
        scores = [round(s, 3) for s in d.val_aggregate_scores]
        summary = f"candidates {len(scores)}; val scores {scores}; best {d.best_idx}"
    else:
        best = best_seen.best[1] or seed_prompt
        summary = f"stopped by the cost meter; best val score seen {best_seen.best[0]:.3f}"
    (HERE / a.out).write_text(best, encoding="utf-8")
    secs = time.time() - t0
    lines = [time.strftime("%Y-%m-%d %H:%M:%S"), summary,
             f"calls {meter.calls}; tokens in {meter.tokens['in']}, out {meter.tokens['out']}",
             f"cost {meter.spent:.6f} CAD; {secs:.0f} s; wrote {a.out} ({short(best)}, {len(best)} characters)"]
    if stopped:
        lines.insert(1, stopped)
    (HERE / "logs").mkdir(exist_ok=True)
    with (HERE / "logs" / "optimize.log").open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")
    print("\n".join(lines[1:]))
    return 3 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
