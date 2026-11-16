"""An Inspect eval in about 25 lines: a dataset of cases, a solver that calls the model, a scorer written in code.

    uv run inspect eval eval_minimal.py

task.py is the same eval with the tutorial's options (which split, which prompt file, a cost score).
"""
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, accuracy, scorer
from inspect_ai.solver import generate, system_message

import gateway  # the course LLM gateway as an Inspect model; your project can use any Inspect model
import scoring  # the tutorial's cases and SQL checker


@scorer(metrics=[accuracy()])
def sql_check():
    async def score(state, target):  # runs the model's SQL and compares with the reference value
        value, _kind, explanation = scoring.check(state.output.completion, state.metadata)
        return Score(value=value, explanation=explanation)
    return score


@task
def minimal():
    cases = scoring.cases("test")  # the held-out cases
    dataset = [Sample(input=c["question"], target=str(c["reference_value"]), metadata=c) for c in cases]
    prompt = open("prompt.txt", encoding="utf-8").read()
    return Task(dataset=dataset, solver=[system_message(prompt), generate()], scorer=sql_check(),
                model=gateway.inspect_model())
