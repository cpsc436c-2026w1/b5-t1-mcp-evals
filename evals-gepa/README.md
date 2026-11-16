# B5T1 part B: evals and prompt optimisation

In this part of the tutorial, you eval a prompt on held-out cases, read and name its failures, let GEPA rewrite the
prompt, eval the new prompt on the same cases, and price the session.

The task: a model writes one DuckDB SQL query to answer a question about 300 made-up taxi trips in
[`data/trips.csv`](data/trips.csv). A case passes when the number the query returns matches the reference within
1%. Code in [`scoring.py`](scoring.py) checks the answer. A model does not judge it.

**Words used below**

- **Case:** one question with its reference SQL and reference value, one line of [`data/cases.jsonl`](data/cases.jsonl).
- **Split:** a group of cases. GEPA learns from `train` (9 cases) and chooses between prompts with `val`
  (9 cases).
- **Held-out:** kept apart from optimisation. The `test` split has 12 held-out cases; GEPA does not read them.
- **Task model:** `qwen3.6-35b-a3b`, the model that answers the cases.
- **Reflection model:** `qwen3.8-27b`, the model that uses failures to propose prompt changes.
- **Course LLM gateway:** a model gateway that passes calls to the models and counts their cost against your token.
- **Eval:** a run of a prompt on the cases of a split, with a score for each case.
- **Inspect:** the library that runs the eval and provides a viewer for its results.
- **GEPA:** a prompt optimiser. Here `dspy.GEPA` uses train cases to propose and test changes and val cases to
  choose a prompt.

The notebook [`tutorial.ipynb`](tutorial.ipynb) has the same steps as cells; Section 2 explains how to open it.

> ⚠️ **Where commands run.** Run every command in a terminal on your laptop, in the tutorial repo's `evals-gepa` folder.
> Use a browser tab on your laptop for `inspect view`, or use [`tutorial.ipynb`](tutorial.ipynb) with this folder's `.venv` kernel.

## 1. Before you start

1. Complete part A, or have your course MCP token ready.
2. Install uv from <https://docs.astral.sh/uv/getting-started/installation/>.
3. Use the same tutorial repository as part A, cloned or downloaded from the course page.

## 2. Set up (once)

1. In a terminal, go into `evals-gepa`. If you are in `mcp`, run:

   ```bash
   cd ../evals-gepa
   ```

   If you are at the tutorial repository root, run `cd evals-gepa`.

2. Set the same token as in part A. On GitHub, in your team repository, find it in the issue **Your course MCP tokens**.
   If you are using the terminal from part A and already set the token there, skip this command.

   In the terminal, in the `evals-gepa` folder, run the command for your system.

   macOS or Linux:

   ```bash
   export KB_MCP_TOKEN='paste-your-token'
   ```

   Windows PowerShell:

   ```powershell
   $env:KB_MCP_TOKEN = 'paste-your-token'
   ```

   Set the token again in each new terminal. Keep it private.

3. In the terminal, in the `evals-gepa` folder, install the packages:

   ```bash
   uv sync
   ```

   uv picks Python 3.13 for this folder and downloads it if needed. You should see the packages install and the
   command finish without an error in the terminal.

4. In the terminal, in the `evals-gepa` folder, check the course LLM gateway:

   ```bash
   uv run python check_gateway.py
   ```

   You should see output like the following in the terminal. The reply, token counts and cost can vary.

   ```text
   gateway: https://oay6tcpsuv4gn5mubtlj7rnbl40gmrlv.lambda-url.ca-central-1.on.aws/v1
   estimate: 1 call, at most 40 tokens in and 200 out, at most 0.000022 CAD
   ✓ KB_MCP_TOKEN is set
   ✓ models your key may use: qwen3-embedding-0.6b, qwen3.6-35b-a3b, qwen3.8-27b
   ✓ reply from qwen3.6-35b-a3b: 'ok'
   ✓ cost of this call: 0.000001 CAD (18 tokens in, 2 out)
   OK: the gateway works with your token.
   ```

   If you see `PROBLEM:` in the terminal, follow the sentence after it. If the problem remains, ask your TA. Do not share your
   token. A `429` can mean the token budget cannot cover the reserve for a call or the per-minute request limit
   has been reached.

**Open the notebook (optional).** The README steps and notebook cells are the same steps. Use either.

In VS Code on your laptop, open [`tutorial.ipynb`](tutorial.ipynb), choose **Select Kernel**, and select this folder's `.venv`.
Alternatively, run the following in a terminal on your laptop, in the tutorial repo's `evals-gepa` folder:

```bash
uv run --with jupyterlab jupyter lab
```

In JupyterLab, open [`tutorial.ipynb`](tutorial.ipynb). You should see the notebook cells.

If a cell fails with `No module named 'inspect_ai'`, the kernel is not this folder's `.venv`. An older kernel named
"Python 3" on your laptop can hide the correct environment. Run the following once in a terminal on your laptop,
in the tutorial repo's `evals-gepa` folder:

```bash
uv run python -m ipykernel install --user \
  --name evals-gepa --display-name "evals-gepa (.venv)"
```

In the notebook, choose the kernel `evals-gepa (.venv)`. Run the cell again. You should see the cell import `inspect_ai` without an error.

## 3. Steps

### Step 1: run the starting prompt

<details>
<summary>What happens when you do this step</summary>

```text
prompt.txt + held-out test cases -> task model -> SQL -> code scorer
```

Inspect runs the task model once per case with [`prompt.txt`](prompt.txt) as its system prompt. The code scorer runs the
SQL and compares its number with the reference.

</details>

1. Open [`prompt.txt`](prompt.txt) in your editor and read it: this is the system prompt the task model gets.
2. In your editor, open [`data/cases.jsonl`](data/cases.jsonl) and read the `question` of three or four rows whose `split` is
   `test`. These are the held-out cases the eval runs.
3. **Predict:** Write down whether you expect the starting prompt to pass below half, about half, or more than half
   of the held-out cases. What kind of question do you think might fail, given what the prompt says and does not
   say about the table?
4. In the terminal, in the `evals-gepa` folder, run the eval:

   ```bash
   uv run inspect eval task.py -T split=test -T prompt=prompt.txt
   ```

   You should see the test cases run in the terminal. A score appears in the terminal box at the end. In the terminal,
   scroll the score away or cover it; you will read it in Step 2.

<details>
<summary>Check your predictions</summary>

The score is the fraction of held-out cases that pass. Each case contributes the same share. In L15, an Inspect
eval has a dataset, a solver and a scorer: here the cases supply inputs and targets, the task model supplies SQL, and
code checks the result.
</details>

### Step 2: read and name the failures

<details>
<summary>What happens when you do this step</summary>

```text
held-out run -> failed cases -> failure names -> score
```

</details>

In the browser tab that `uv run inspect view` opens, you will read the failed cases before you look at the score,
so the aggregate does not direct your error analysis. Treat the reference SQL and value as correct for this data.
When the model's query differs from the reference SQL, name what the query did differently.

A failure name is short and says what to fix. After reading a failed case in the viewer, invent a name for its failure.
Reuse that name when another case fails in the same way.

**Predict:** In your notes, write down whether you expect several failed cases to share a failure name or each
failed case to need its own name.

1. In the terminal, in the `evals-gepa` folder, start the viewer:

   ```bash
   uv run inspect view
   ```

   You should see a browser address in the terminal. Open that address in a browser tab. You should see either the
   run's page or a table of runs.
2. In the browser tab that `uv run inspect view` opened, if you see a table of runs, click the newest run's row.
   The newest run has the latest COMPLETED time. Do not look at the SCORE column yet. You should see the run's page.
   On that page, do not look at the `Scorer`/`accuracy` box at the top right yet. In the SAMPLES tab, click each
   row whose SQL_CHECK is 0. You should see the case's page. On the case's page, read INPUT and ANSWER. Open
   SCORING and read EXPLANATION in the `sql_check` row. Use the run name at the top left to return to the run's page.
3. In your notes, fill in the table in your own words. Use the same name when cases fail in the same way. Add a row for every
   failed case.

   | case id | what went wrong | name of the failure |
   |---|---|---|
   | | | |
   | | | |
   | | | |

4. In the browser tab, read the score in the `Scorer`/`accuracy` box at the top right of the run's page. Alternatively,
   read the score in the box at the end of the Step 1 terminal output. In your notes, count how many cases each
   failure name covers. Press Ctrl+C in the viewer terminal to stop the viewer.

<details>
<summary>Check your predictions</summary>

Cases with the same failure should have the same name, and the counts across your names should add up to the
number of failed cases. Reading the failures before the score is error analysis: the cases tell you what to change,
and the score only tells you how many cases need it.
</details>

### Step 3: let GEPA rewrite the prompt

<details>
<summary>What happens when you do this step</summary>

```text
train cases -> failures -> reflection model -> prompt candidates -> val cases -> selected prompt
```

GEPA uses train cases and their feedback to propose and test prompt changes. It keeps a Pareto set of candidates
that each do best on some examples and returns a prompt selected using val scores; GEPA does not read the test
cases.

</details>

**Predict:** In your notes, write down whether you expect the new prompt to address none, some or all of your
failure names. Do you expect the new prompt to state, in its own words, a rule you found in Step 2?

1. In the terminal, in the `evals-gepa` folder, run:

   ```bash
   uv run python optimize.py
   ```

   You should see the estimate first in the terminal, followed by progress bars and log lines such as
   `Iteration 1: Proposed new text for predict:` with each new prompt.
2. In the terminal output at the end, look for lines like `candidates 2; val scores [...]; best 1`, the calls, and
   `cost ... CAD; ... s; wrote prompt.optimized.txt`. In your editor's `evals-gepa` folder file list, you should
   see `prompt.optimized.txt` next to [`prompt.txt`](prompt.txt).

   The cost meter in [`optimize.py`](optimize.py) stops GEPA before any call that could take it past 0.05 CAD.

<details>
<summary>Check your predictions</summary>

GEPA uses train and val cases. It does not read any held-out test case. L17's evaluator-optimizer
pattern uses feedback to propose revisions and a limit to stop attempts. A prompt change can address a failure
without guaranteeing a better held-out score.
</details>

### Step 4: read the new prompt

<details>
<summary>What happens when you do this step</summary>

```text
prompt.txt + prompt.optimized.txt -> added lines -> failure names and data check
```

A prompt can improve an eval and still contain a rule that is not true of the data. Read the added lines before
using the prompt and check their claims.

</details>

**Predict:** Write down whether you expect every failure name in your table to be addressed, and whether you
expect every added rule to be true of the data.

1. In your editor, open `prompt.optimized.txt` and [`prompt.txt`](prompt.txt) side by side. You should see the starting instructions and any
   changes GEPA made.
2. For each added line in the editor, write down in your notes which failure name from your Step 2 table it addresses.
   In your notes, mark any name that the new prompt does not address.
3. In your editor, open [`data/build.py`](data/build.py), the data script. Choose one rule from
   `prompt.optimized.txt` in the editor and check whether the script supports it. In your notes,
   mark whether each added line is true of the data, and mark any claim you cannot verify.

<details>
<summary>Check your predictions</summary>

An added line can address a failure name, leave a name unaddressed, or make a claim you cannot verify from the
data script. L17's evaluator-optimizer pattern checks a result against criteria. A reader still needs to check
claims before using the prompt.
</details>

### Step 5: eval the new prompt

<details>
<summary>What happens when you do this step</summary>

```text
prompt.optimized.txt + same held-out test cases -> task model -> code scorer
```

Run the same eval on the same test split so the scores and individual cases can be compared. GEPA selected a
prompt using val cases, so the held-out cases provide a separate check.

</details>

**Predict:** Write down whether you expect the held-out score to be higher, lower, or about the same, and whether
you expect the same or fewer failures.

1. In the terminal, in the `evals-gepa` folder, run:

   ```bash
   uv run inspect eval task.py -T split=test -T prompt=prompt.optimized.txt
   ```

   You should see a score in the terminal box at the end of the eval.
2. In the terminal, in the `evals-gepa` folder, run `uv run inspect view`. You should see a browser address in the
   terminal. Open that address in a browser tab. You should see a table of runs. Click the row with TASK
   `sql_test_prompt_optimized`. You should see the new prompt's run page.
   In the SAMPLES tab, click each row whose SQL_CHECK is 0. On each case's page, read INPUT and ANSWER. Open
   SCORING and read EXPLANATION in the `sql_check` row. Use the run name at the top left to return to the run's page.
   Compare the remaining failures in the browser with the names in your Step 2 table in your notes. Does each
   remaining failure have a name in your table? If none fail, which of your names did the new prompt fix?
3. Compare the score in the `Scorer`/`accuracy` box on the new run's page with the Step 2 score in your notes or
   the Step 1 terminal output. Compare the failures in the new run's SAMPLES tab with your Step 2 table in your
   notes. Press Ctrl+C in the viewer terminal to stop the viewer.

<details>
<summary>Check your predictions</summary>

Compare whether the after score is at least the before score and whether the new prompt has the same or fewer
failures. Either relation can fail on a particular run. L17 uses held-out cases because GEPA chose the prompt on
validation cases, so the held-out score checks questions outside that choice.
</details>

### Step 6: price the session

<details>
<summary>What happens when you do this step</summary>

```text
upper-bound estimate -> eval and GEPA records -> actual cost comparison
```

</details>

Your token's term budget is 2 CAD. The course rule for one whole run (check, eval, GEPA, eval again) is less than
0.10 CAD. [`budget.py`](budget.py) prints an upper-bound estimate of the calls and their cost before any call. [`optimize.py`](optimize.py)
printed an estimate at the start of Step 3. [`compare.py`](compare.py) reads `logs/` and reports the actual cost.

1. In the terminal, in the `evals-gepa` folder, print the estimate again with [`budget.py`](budget.py):

   ```bash
   uv run python budget.py
   ```

   You should see the upper-bound calls and cost for the whole run in the terminal output.
2. **Predict:** In your notes, write down how far below this estimate you expect the recorded total to be: about
   the same, around half, or a small fraction. Do you expect the whole session to cost a few cents or less?
3. In the terminal, in the `evals-gepa` folder, compare the recorded runs with [`compare.py`](compare.py):

   ```bash
   uv run python compare.py
   ```

   You should see one line per eval run in the terminal output with when, split, prompt, cases, score and cost in CAD, followed by
   `GEPA (logs/optimize.log): ... CAD`, `cost of everything in logs/: ... CAD`, and
   `held-out cases: before ..., after ...`. The last check says
   `check: the after score is at least the before score on the held-out cases: yes` or ends in `NO`.

   Each Inspect eval also prints a `cost_cad` score rounded to three decimals, so it often shows `0.000`.
   [`optimize.py`](optimize.py) prints GEPA's cost and records it in `logs/optimize.log`. The gateway check prints the cost
   of its own call.

4. Compare the recorded total in the `compare.py` terminal output with the estimate in the `budget.py` terminal
   output. With 12 test cases, one case is about 8 points of the score;
   a small difference can come from chance.

<details>
<summary>Check your predictions</summary>

The recorded total should be below the upper-bound estimate for the corresponding run. L17's course LLM gateway
reserves the most a call can cost before the call and replaces the reserve with the actual cost after the reply;
bounded attempts help keep spending within a limit.
</details>

## 4. Extra exercises

**Compare another GEPA run.** In the terminal, in the `evals-gepa` folder, save the first optimised prompt under another name. In macOS or Linux:

```bash
cp prompt.optimized.txt prompt.first.txt
```

In PowerShell:

```powershell
Copy-Item prompt.optimized.txt prompt.first.txt
```

In your editor's `evals-gepa` folder file list, you should see `prompt.first.txt`.

**Predict:** will a second GEPA run with another seed write the same prompt, a similar one, or a different one?
In the terminal, in the `evals-gepa` folder, run `uv run python optimize.py --seed 1`. You should see the estimate,
progress and final lines in the terminal. In your editor, open `prompt.optimized.txt` and
`prompt.first.txt` side by side. Which lines are the same, and which differ?

<details>
<summary>Check your answer</summary>

The prompts can share instructions and still differ in other lines. GEPA proposes and tests candidates, so a
different seed can lead to a different prompt. Compare the prompts and their evals rather than assuming they are
equal.
</details>

**Eval on train.** Predict whether the score on cases GEPA read will be higher than, lower than, or about the
same as the held-out score. In the terminal, in the `evals-gepa` folder, run:

```bash
uv run inspect eval task.py -T split=train -T prompt=prompt.optimized.txt
```

You should see the train score in the terminal box at the end of the eval. Compare that score with the held-out
score for the prompt you evaluated in the Step 5 terminal box or on the new run's page in the viewer.

<details>
<summary>Check your prediction</summary>

The train score can be higher, lower or about the same as the held-out score. GEPA used train cases during
optimisation, so their score says less about performance on new questions than a score on cases GEPA did not read.
</details>

## 5. Clean up

`logs/` and `prompt.optimized.txt` are yours to delete. Git ignores them. The `.venv` takes about 350 MB. If you
delete it, `uv sync` rebuilds it. Keep your token: the project uses it.

## 6. Recap and reflection

<details>
<summary>What you did, why, and how the same work runs outside this tutorial (open after the tutorial)</summary>

- **You ran an eval.** Cases, a solver and a code scorer gave repeatable checks. Outside the tutorial, teams can
  use the same structure to check an application's outputs.
- **You named failures.** Reading individual cases showed what a score alone could not. Teams can group failures
  before deciding what to change.
- **You used GEPA.** A reflection model proposed prompt changes from feedback and val cases helped select a
  candidate. Teams can use bounded evaluator-optimizer loops to revise instructions.
- **You checked the new prompt.** An added rule needs evidence in the data. Teams should verify generated
  instructions before using them.
- **You compared held-out results.** GEPA did not read the test cases. Teams can keep separate cases for a check
  on questions outside optimisation.
- **You priced the session.** An estimate bounded possible spending and logs recorded actual cost. Applications
  can set limits before calls and monitor spending afterwards.

**Reflection:**

1. Which failure name would you investigate next, and what extra case would help?
2. What evidence would you want before using the optimised prompt on a different dataset?

</details>

## If you fall behind

Ask a TA which steps to do first. Always do Step 2 (read the failures) before Step 3 (GEPA), and Step 4 (read the
new prompt) before Step 5 (evaluate again): the order is the point of the tutorial. If you are short of time after
Step 2, `uv run python run_all.py` runs the remaining commands in one go; then do Step 4 by comparing the prompt files.

## Practise without a token

[`stand_in_gateway.py`](stand_in_gateway.py) is a local server that acts like the course LLM gateway, with canned answers and no
money charged. Start it in one terminal with `uv run python stand_in_gateway.py`. In a second terminal, set
these two variables and run the steps:

| macOS or Linux | Windows (PowerShell) |
|---|---|
| `export COURSE_GATEWAY_URL=http://127.0.0.1:8765/v1` | `$env:COURSE_GATEWAY_URL = "http://127.0.0.1:8765/v1"` |
| `export KB_MCP_TOKEN=stand-in-token` | `$env:KB_MCP_TOKEN = "stand-in-token"` |

To return to the real course LLM gateway, delete the `logs` folder, which holds the stand-in runs, open a new
terminal and set only your token. `uv run pytest -q` runs the tests against the stand-in.

## Files

| File | What it is |
|---|---|
| [`tutorial.ipynb`](tutorial.ipynb) | The same steps as notebook cells. |
| [`prompt.txt`](prompt.txt) | The starting prompt. |
| [`data/cases.jsonl`](data/cases.jsonl), [`data/trips.csv`](data/trips.csv) | The cases with their splits and the table they ask about; `data/build.py` writes both. |
| [`data/build.py`](data/build.py) | The script that makes the data and cases. |
| [`task.py`](task.py) | The Inspect task: one split and the prompt from a file, scored by `scoring.py`. |
| [`scoring.py`](scoring.py) | Code that checks the SQL result against the reference. |
| [`optimize.py`](optimize.py) | `dspy.GEPA` on train and val, with the cost meter. |
| [`gateway.py`](gateway.py) | The gateway address, token, prices, retries and plain error messages. |
| [`budget.py`](budget.py), [`compare.py`](compare.py), [`run_all.py`](run_all.py), [`check_gateway.py`](check_gateway.py) | The estimate, comparison, whole run and check. |
| [`stand_in_gateway.py`](stand_in_gateway.py) | A local stand-in for practice without a token. |
