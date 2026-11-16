# B5T1 part B: evals and prompt optimisation

In this part of the tutorial, you eval a prompt on held-out cases, read and name its failures, let GEPA rewrite the
prompt, eval the new prompt on the same cases, and price the session. Allow about 30 minutes to read
and compare the results. The commands take about two minutes of machine time in total.

The task: a model writes one DuckDB SQL query to answer a question about 300 made-up taxi trips in
[`data/trips.csv`](data/trips.csv). A case passes when the number the query returns matches the reference within
1%. Code in [`scoring.py`](scoring.py) checks the answer. A model does not judge it.

**Words used below**

- **Case:** one question with its reference SQL and reference value, one line of `data/cases.jsonl`.
- **Split:** a group of cases. GEPA learns from `train` (9 cases) and chooses between prompts with `val`
  (9 cases).
- **Held-out:** kept apart from optimisation. The `test` split has 12 held-out cases; GEPA does not read them.
- **Worker model:** `qwen3.6-35b-a3b`, the model that answers the cases.
- **Reflection model:** `qwen3.8-27b`, the model that uses failures to propose prompt changes.
- **Course LLM gateway:** a model gateway that passes calls to the models and counts their cost against your token.
- **Eval:** a run of a prompt on the cases of a split, with a score for each case.
- **Inspect:** the library that runs the eval and provides a viewer for its results.
- **GEPA:** a prompt optimiser. Here `dspy.GEPA` uses train cases to propose and test changes and val cases to
  choose a prompt.

The notebook `tutorial.ipynb` has the same steps as cells; Section 2 explains how to open it.

## 1. Before you start

1. Complete part A, or have your course MCP token ready.
2. Install uv from <https://docs.astral.sh/uv/getting-started/installation/>.
3. Use the same tutorial repository as part A, cloned or downloaded from the course page.

## 2. Set up (once, about 5 minutes)

1. In a terminal, go into `evals-gepa`. If you are in `mcp`, run:

   ```bash
   cd ../evals-gepa
   ```

   If you are at the tutorial repository root, run `cd evals-gepa`.

2. Set the same token as in part A. Find it in the issue **Your course MCP tokens** in your team repository.
   If you are using the terminal from part A and already set the token there, skip this command.

   macOS or Linux:

   ```bash
   export KB_MCP_TOKEN='paste-your-token'
   ```

   Windows PowerShell:

   ```powershell
   $env:KB_MCP_TOKEN = 'paste-your-token'
   ```

   Set the token again in each new terminal. Keep it private.

3. Install the packages:

   ```bash
   uv sync
   ```

   uv picks Python 3.13 for this folder and downloads it if needed. You should see the packages install and the
   command finish without an error.

4. Check the course LLM gateway:

   ```bash
   uv run python check_gateway.py
   ```

   You should see output like the following. The reply, token counts and cost can vary.

   ```text
   gateway: https://oay6tcpsuv4gn5mubtlj7rnbl40gmrlv.lambda-url.ca-central-1.on.aws/v1
   estimate: 1 call, at most 40 tokens in and 200 out, at most 0.000022 CAD
   ✓ KB_MCP_TOKEN is set
   ✓ models your key may use: qwen3-embedding-0.6b, qwen3.6-35b-a3b, qwen3.8-27b
   ✓ reply from qwen3.6-35b-a3b: 'ok'
   ✓ cost of this call: 0.000001 CAD (18 tokens in, 2 out)
   OK: the gateway works with your token.
   ```

   If you see `PROBLEM:`, follow the sentence after it. If the problem remains, ask your TA. Do not share your
   token. A `429` can mean the token budget cannot cover the reserve for a call or the per-minute request limit
   has been reached.

**Open the notebook (optional).** In VS Code, open `tutorial.ipynb`, choose **Select Kernel**, and select the
`.venv` of this folder. Alternatively, in a terminal in this folder, run
`uv run --with jupyterlab jupyter lab` and open `tutorial.ipynb`. If the kernel cannot import `inspect_ai`, it
is not using this folder's `.venv`; choose that environment again. The README steps and the notebook cells are
the same steps. Use either.

## 3. Steps

### Step 1: run the starting prompt

```text
prompt.txt + held-out test cases -> worker model -> SQL -> code scorer
```

Inspect runs the worker model once per case with `prompt.txt` as its system prompt. The code scorer runs the
SQL and compares its number with the reference.

**Predict:** Write down whether you expect the starting prompt to pass below half, about half, or more than half
of the held-out cases. What kind of question do you think might fail?

1. Open `prompt.txt` in your editor and read it.
2. Run the eval:

   ```bash
   uv run inspect eval task.py -T split=test -T prompt=prompt.txt
   ```

   You should see the test cases run in under a minute. A score appears at the end. Scroll it away or cover it;
   you will read it in Step 2.

<details>
<summary>Check your predictions</summary>

The score is the fraction of held-out cases that pass. Each case contributes the same share. In L15, an Inspect
eval has a dataset, a solver and a scorer: here the cases supply inputs and targets, the worker supplies SQL, and
code checks the result.
</details>

### Step 2: read and name the failures

```text
held-out run -> failed cases -> failure names -> score
```

Read the cases before the score so the aggregate does not direct your error analysis. A failure name is short
and says what to fix. Invent each name after reading a failed case, and reuse it when another case fails in the
same way.

**Predict:** Write down whether you expect several failed cases to share a failure name, or each failure to need
a different name.

1. Start the viewer:

   ```bash
   uv run inspect view
   ```

   Open the browser link it prints. You should see a list of runs.
2. Open the newest run. Before looking at its score, click each case whose `sql_check` is 0. Read the question,
   the worker model's reply and the explanation.
3. Fill in the table in your own words. Use the same name when cases fail in the same way. Add a row for every
   failed case.

   | case id | what went wrong | name of the failure |
   |---|---|---|
   | | | |
   | | | |
   | | | |

4. Read the score at the top of the run in the viewer, or at the end of the Step 1 terminal output. Count how
   many cases each failure name covers. Press Ctrl+C in the viewer terminal to stop the viewer.

<details>
<summary>Check your predictions</summary>

Cases with the same failure should have the same name, and the counts across your names should add up to the
number of failed cases. Reading the failures before the score is error analysis: the cases tell you what to change,
and the score only tells you how many cases need it.
</details>

### Step 3: let GEPA rewrite the prompt

```text
train cases -> failures -> reflection model -> prompt candidates -> val cases -> selected prompt
```

GEPA uses train cases and their feedback to propose and test prompt changes. It keeps a Pareto set of candidates
that each do best on some examples and returns a prompt selected using val scores; GEPA does not read the test
cases.

**Predict:** Write down whether you expect the new prompt to address at least one of your failure names. Do you
expect GEPA to consult the held-out cases?

1. Run:

   ```bash
   uv run python optimize.py
   ```

   You should see the estimate first, progress bars and log lines such as
   `Iteration 1: Proposed new text for predict:` with each new prompt. The run takes about a minute, longer
   when the gateway is busy.
2. At the end, look for lines like `candidates 2; val scores [...]; best 1`, the calls, and
   `cost ... CAD; ... s; wrote prompt.optimized.txt`. The file `prompt.optimized.txt` should now be next to
   `prompt.txt`.

   The cost meter in `optimize.py` stops GEPA before any call that could take it past 0.05 CAD.

<details>
<summary>Check your predictions</summary>

GEPA uses train and val cases. It does not read any held-out test case. L17's evaluator-optimizer
pattern uses feedback to propose revisions and a limit to stop attempts. A prompt change can address a failure
without guaranteeing a better held-out score.
</details>

### Step 4: read the new prompt

```text
prompt.txt + prompt.optimized.txt -> added lines -> failure names and data check
```

A prompt can improve an eval and still contain a rule that is not true of the data. Read the added lines before
using the prompt and check their claims.

**Predict:** Write down whether you expect every failure name in your table to be addressed, and whether you
expect every added rule to be true of the data.

1. Open `prompt.optimized.txt` and `prompt.txt` side by side. You should see the starting instructions and any
   changes GEPA made.
2. For each added line, write down which of your failure names it addresses. Note any name that the new prompt
   does not address.
3. Open `data/build.py`, the script that made the data. Choose one rule GEPA wrote and check whether the script
   supports it. Ask whether every added line is true of the data. Mark any claim you cannot verify.

<details>
<summary>Check your predictions</summary>

An added line can address a failure name, leave a name unaddressed, or make a claim you cannot verify from the
data script. L17's evaluator-optimizer pattern checks a result against criteria. A reader still needs to check
claims before using the prompt.
</details>

### Step 5: eval the new prompt

```text
prompt.optimized.txt + same held-out test cases -> worker model -> code scorer
```

Run the same eval on the same test split so the scores and individual cases can be compared. GEPA selected a
prompt using val cases, so the held-out cases provide a separate check.

**Predict:** Write down whether you expect the held-out score to be higher, lower, or about the same, and whether
you expect the same or fewer failures.

1. Run:

   ```bash
   uv run inspect eval task.py -T split=test -T prompt=prompt.optimized.txt
   ```

   The eval takes under a minute and ends with a score.
2. Run `uv run inspect view` and open the browser link and newest run. You should see the new prompt's results.
   Read the question, reply and explanation for any case whose `sql_check` is 0. Does each remaining failure
   have a name in your table? If none fail, which of your names did the new prompt fix?
3. Compare the score and failures with Step 2. Press Ctrl+C in the viewer terminal to stop the viewer.

<details>
<summary>Check your predictions</summary>

Compare whether the after score is at least the before score and whether the new prompt has the same or fewer
failures. Either relation can fail on a particular run. L17 uses held-out cases because GEPA chose the prompt on
validation cases, so the held-out score checks questions outside that choice.
</details>

### Step 6: price the session

```text
upper-bound estimate -> eval and GEPA records -> actual cost comparison
```

Your token's term budget is 2 CAD. The course rule for one whole run (check, eval, GEPA, eval again) is less than
0.10 CAD. `budget.py` prints an upper-bound estimate of the calls and their cost before any call is made, and
`optimize.py` printed the same kind of estimate at the start of Step 3. `compare.py` reads the records in `logs/`
and reports what the calls actually cost.

**Predict:** Write down whether you expect the recorded total to be above or below the
upper-bound estimate.
Do you expect a few cents or less?

1. Print the estimate again:

   ```bash
   uv run python budget.py
   ```

   You should see the upper-bound calls and cost for the whole run.
2. Compare the recorded runs:

   ```bash
   uv run python compare.py
   ```

   You should see one line per eval run with when, split, prompt, cases, score and cost in CAD, followed by
   `GEPA (logs/optimize.log): ... CAD`, `cost of everything in logs/: ... CAD`, and
   `held-out cases: before ..., after ...`. The last check says
   `check: the after score is at least the before score on the held-out cases: yes` or ends in `NO`.

   Each Inspect eval also prints a `cost_cad` score rounded to three decimals, so it often shows `0.000`.
   `optimize.py` prints GEPA's cost and records it in `logs/optimize.log`. The gateway check prints the cost
   of its own call.

3. Compare the recorded total with the estimate. With 12 test cases, one case is about 8 points of the score;
   a small difference can come from chance.

<details>
<summary>Check your predictions</summary>

The recorded total should be below the upper-bound estimate for the corresponding run. L17's course LLM gateway
reserves the most a call can cost before the call and replaces the reserve with the actual cost after the reply;
bounded attempts help keep spending within a limit.
</details>

## 4. Extra exercises

**Compare another GEPA run.** Save the first optimised prompt under another name. In macOS or Linux:

```bash
cp prompt.optimized.txt prompt.first.txt
```

In PowerShell:

```powershell
Copy-Item prompt.optimized.txt prompt.first.txt
```

Run `uv run python optimize.py --seed 1` and compare the new `prompt.optimized.txt` with `prompt.first.txt`.
Which lines are the same, and which differ?

<details>
<summary>Check your answer</summary>

The prompts can share instructions and still differ in other lines. GEPA proposes and tests candidates, so a
different seed can lead to a different prompt. Compare the prompts and their evals rather than assuming they are
equal.
</details>

**Eval on train.** Predict whether the score on cases GEPA read will be higher than, lower than, or about the
same as the held-out score. Run:

```bash
uv run inspect eval task.py -T split=train -T prompt=prompt.optimized.txt
```

Compare the train score with the held-out score for the prompt you evaluated.

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

Run `uv run python run_all.py`. It does the setup check and Steps 1, 3, 5 and 6. Then do Steps 2 and 4 by
reading the runs in `uv run inspect view` and comparing the prompt files.

## Practise without a token

`stand_in_gateway.py` is a local server that acts like the course LLM gateway, with canned answers and no
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
