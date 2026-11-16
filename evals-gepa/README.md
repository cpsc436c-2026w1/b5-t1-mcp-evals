# evals-gepa: eval a prompt, let GEPA rewrite it, eval it again

In this part of the tutorial you run a small eval of a prompt, read its failures, let an optimiser rewrite the
prompt, and run the eval again on cases the optimiser never saw. It takes about 30 minutes. The whole run costs a
few cents of your 2 CAD course budget at most, and the scripts print the cost as they go.

The task: a model writes one DuckDB SQL query to answer a question about 300 made-up taxi trips
(`data/trips.csv`). A case passes when the number the query returns matches the reference. Code checks this, no
model judges it (`scoring.py`).

Words used below:

- **case**: one question with its reference SQL and reference value, one line of `data/cases.jsonl`.
- **split**: each case is in one of three groups. GEPA learns from `train` (9 cases) and chooses between prompts
  with `val` (9 cases). `test` (12 cases) is **held out**: GEPA never sees it, so its score tells you how the new
  prompt does on new questions.
- **worker model**: `qwen3.6-35b-a3b`, the model that answers the cases.
- **gateway**: the course server that passes your calls on to the models and counts their cost against your token.
- **eval**: a run of a prompt on the cases of one split, with a score for each case. **Inspect** is the library
  that runs it and shows the results in a viewer.
- **GEPA**: an optimiser for prompts (here `dspy.GEPA`, from the DSPy library). It runs the prompt on a few train cases, gives the failures to a second
  model (the **reflection model**, `qwen3.8-27b`), which writes a new prompt. It keeps a new prompt if it beats
  the old one on those few cases, and repeats until its budget of calls is used. At the end it returns the prompt
  with the best val score.

## Before the tutorial: set up (10 minutes, needs Wi-Fi)

Install uv (<https://docs.astral.sh/uv/getting-started/installation/>). Get the tutorial repository from the course
page (clone it or download it), then in a terminal go into its `evals-gepa` folder (`cd evals-gepa`) and run:

```bash
uv sync
```

You should see uv install the packages and end without an error.

## Steps

**1. Set your course token.** Use the token from the course page. Do this in every new terminal.

| macOS (Terminal) | Windows (PowerShell) |
|---|---|
| `export KB_MCP_TOKEN="paste-your-token"` | `$env:KB_MCP_TOKEN = "paste-your-token"` |

**2. See the estimate before any call.** Run `uv run python budget.py`. You should see the number of calls and the
cost in CAD of each step, and a total below the course limit of 0.10 CAD.

**3. Check the gateway.** Run `uv run python check_gateway.py`. You should see the three models your key may use,
a short reply, and a line with the tokens in and out and a cost below 0.0001 CAD. If you see `PROBLEM:`, the sentence
after it says what to fix.

**4. Run the eval on the held-out cases with the starting prompt.** Open `prompt.txt` and read it first. Then run:

```bash
uv run inspect eval task.py -T split=test -T prompt=prompt.txt
```

You should see the 12 cases run in under a minute. The run ends with a score. Do not read it yet.

**5. Read the failures and name them, before you look at the score.** Run `uv run inspect view` and open the
browser link it prints. Open the newest run and click each case whose `sql_check` is 0. Read the
question, the model's reply and the explanation. Then fill this table, one row per failed case, in your own words:

| case id | what went wrong | name of the failure |
|---|---|---|
| h__ | | |
| h__ | | |
| h__ | | |

A name is short and says what to fix, for example "text after the SQL" or "wrong code for cash". When two cases
fail the same way, give them the same name. Now read the score (at the end of the step 4 output in the terminal, or at the top of the run in the
viewer), and count how many cases each name covers.
Press Ctrl+C in the terminal to stop the viewer.

**6. Let GEPA rewrite the prompt.** Run `uv run python optimize.py`. GEPA uses only the train and val cases. You
should see the estimate first, then progress bars and lines like `Iteration 1: Proposed new text for predict:`
with each new prompt,
and at the end the val score of every prompt it kept, the cost in CAD and `wrote prompt.optimized.txt`. It takes
2 to 10 minutes. The cost meter stops GEPA before any call that could take it past 0.05 CAD.

**7. Read the new prompt.** Open `prompt.optimized.txt` next to `prompt.txt`. Find each line GEPA added. Which of
your failure names from step 5 does each line address? Is any of your names not addressed?

**8. Run the eval again with the new prompt, on the same held-out cases.**

```bash
uv run inspect eval task.py -T split=test -T prompt=prompt.optimized.txt
```

Run `uv run inspect view` again and read the cases that still fail. Do they have a name from your table?

**9. Compare, and see the cost of the whole run.** Run `uv run python compare.py`. You should see one line per
eval run with its score and its cost in CAD, the cost of GEPA, the total, and this check:

> the after score is at least the before score on the held-out cases

Is it true for your run? With only 12 test cases, one case is about 8 points of the score. A small difference
can come from chance.

## Where the cost is printed

- `check_gateway.py`: the cost of its one call.
- each `inspect eval` run: the `cost_cad` score. It rounds to 3 decimals, so it often shows `0.000`.
- `optimize.py`: the cost of GEPA at the end, also in `logs/optimize.log`.
- `compare.py`: every run in full, and the total.

## If you fall behind

Run all steps at once with `uv run python run_all.py`. It does steps 2, 3, 4, 6, 8 and 9. Then do steps 5 and 7 by
reading the runs in `uv run inspect view`.

## Practise without a token

`stand_in_gateway.py` is a local server that acts like the gateway, with canned answers and no cost. Start it in
one terminal with `uv run python stand_in_gateway.py`. In a second terminal, set these two, then run the steps:

| macOS | Windows (PowerShell) |
|---|---|
| `export COURSE_GATEWAY_URL=http://127.0.0.1:8765/v1` | `$env:COURSE_GATEWAY_URL = "http://127.0.0.1:8765/v1"` |
| `export KB_MCP_TOKEN=stand-in-token` | `$env:KB_MCP_TOKEN = "stand-in-token"` |

To go back to the real gateway, delete the `logs` folder (it holds the stand-in runs), open a new terminal
and set only your token. `uv run pytest -q` runs the tests
against the stand-in.

## Files

| file | what it is |
|---|---|
| `prompt.txt` | the starting prompt |
| `data/cases.jsonl`, `data/trips.csv` | the cases with their split, and the table they ask about (`data/build.py` writes both) |
| `task.py` | the Inspect task: one split, the prompt from a file, scored by `scoring.py` |
| `optimize.py` | `dspy.GEPA` on train and val, with the cost meter |
| `gateway.py` | the gateway address, the token, the prices, retries and plain error messages |
| `budget.py`, `compare.py`, `run_all.py`, `check_gateway.py` | the estimate, the comparison, the whole run, the check |
