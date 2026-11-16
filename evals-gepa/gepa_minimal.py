"""GEPA prompt optimisation in about 30 lines: the part to reuse in your own project.

    uv run python gepa_minimal.py

optimize.py runs the same method for the tutorial and adds the course's cost limits, retries and logs. This file
is the core without them. To use it for your own task, change the four places marked YOUR TASK.
"""
import os

import dspy

import gateway  # only for the token, the gateway address and the .env file; your project can read these itself
import scoring  # the tutorial's cases and scorer; YOUR TASK: your own cases and scorer

URL, KEY = gateway.base_url(), gateway.token()

# The task model answers the questions. The reflection model reads the failures and writes a better prompt.
# Give the reflection model room for its reply: a thinking model spends tokens on reasoning before it answers.
task_lm = dspy.LM("openai/" + os.environ.get("TASK_MODEL", "qwen3.6-35b-a3b"), api_base=URL, api_key=KEY,
                  model_type="chat", max_tokens=1024)  # the course LLM gateway serves chat completions
reflection_lm = dspy.LM("openai/" + os.environ.get("GEPA_REFLECTOR", "qwen3.8-27b"), api_base=URL, api_key=KEY,
                        model_type="chat", max_tokens=8192, temperature=1.0)  # GPT models accept only temperature 1.0
dspy.configure(lm=task_lm)

# YOUR TASK: the input and output fields, and the starting instructions.
program = dspy.Predict(dspy.Signature("question -> sql", open("prompt.txt", encoding="utf-8").read()))


# YOUR TASK: a score and, above all, feedback that says what went wrong. GEPA learns from the feedback text.
def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    score, _kind, feedback = scoring.check(pred.sql or "", dict(gold))
    return dspy.Prediction(score=score, feedback=feedback)


# YOUR TASK: your cases. GEPA learns from train and chooses with val; keep a test set it never sees.
train = [dspy.Example(**c).with_inputs("question") for c in scoring.cases("train")]
val = [dspy.Example(**c).with_inputs("question") for c in scoring.cases("val")]

gepa = dspy.GEPA(metric=metric, reflection_lm=reflection_lm, max_metric_calls=40)  # 40 calls of the task model
best = gepa.compile(program, trainset=train, valset=val)

print(best.signature.instructions)  # the new prompt
open("prompt.minimal.txt", "w", encoding="utf-8").write(best.signature.instructions)
