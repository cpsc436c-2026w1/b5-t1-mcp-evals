"""Inspect task: one split of data/cases.jsonl, the system prompt read from a file, scored by code (scoring.py).

    uv run inspect eval task.py -T split=test -T prompt=prompt.txt
    uv run inspect eval task.py -T split=test -T prompt=prompt.optimized.txt
    uv run inspect view

Two scores per case: `sql_check` (1 if the number the SQL returns matches the reference) and `cost_cad` (what the
call cost, in CAD; its metric is the total for the run). The model is TASK_MODEL (default qwen3.6-35b-a3b), at the address in gateway.py."""

from __future__ import annotations

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import SampleScore, Score, Target, accuracy, metric, scorer
from inspect_ai.model import ChatMessageSystem
from inspect_ai.solver import Generate, TaskState, generate, solver

import gateway
import scoring

HERE = Path(__file__).resolve().parent


@solver
def prompt_from_file(text: str):
    """Puts the prompt in as the system message, as is (no template filling: braces in a prompt stay)."""
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.messages.insert(0, ChatMessageSystem(content=text))
        return state
    return solve


@metric
def total():
    def m(scores: list[SampleScore]) -> float:
        return round(sum(s.score.as_float() for s in scores), 6)
    return m


@scorer(metrics=[accuracy()])
def sql_check():
    async def score(state: TaskState, target: Target) -> Score:
        value, kind, feedback = scoring.check(state.output.completion, state.metadata)
        return Score(value=value, answer=state.output.completion[:500], explanation=feedback,
                     metadata={"kind": kind})
    return score


@scorer(metrics=[total()])
def cost_cad(model: str = ""):
    async def score(state: TaskState, target: Target) -> Score:
        u = state.output.usage
        t_in, t_out = (u.input_tokens, u.output_tokens) if u else (0, 0)
        return Score(value=gateway.cad(model, t_in, t_out), metadata={"tokens_in": t_in, "tokens_out": t_out})
    return score


@task
def sql_cases(split: str = "test", prompt: str = "prompt.txt") -> Task:
    """split: train | val | test | all.  prompt: path of the system prompt file."""
    p = Path(prompt) if Path(prompt).is_absolute() else HERE / prompt
    if not p.exists():
        raise gateway.GatewayError(f"prompt file not found: {p}")
    model = gateway.task_model()
    samples = [Sample(id=c["id"], input=c["question"], target=str(c["reference_value"]), metadata=c)
               for c in scoring.cases(split)]
    return Task(dataset=MemoryDataset(samples), solver=[prompt_from_file(p.read_text(encoding="utf-8")), generate()],
                scorer=[sql_check(), cost_cad(model)], model=gateway.inspect_model(model),
                metadata={"split": split, "prompt": p.name}, name=f"sql_{split}_{p.stem.replace('.', '_')}")
