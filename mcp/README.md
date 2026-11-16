# Connect your coding assistant to the course MCP server

MCP (Model Context Protocol) lets your coding assistant call tools on a server. The course MCP server has one job.
It searches the course files (lecture decks, tutorials, readings) and returns the passages it finds, each with its
file path. Its search tool is called `query_kb`.

In this part of the tutorial (about 20 minutes) you set your own token, check it works, connect your assistant, run two
MCP tests and check your project proposal against the course files.

You need `uv`, this folder (`mcp/` in the tutorial repo), your team repo, and Claude Code or Kiro.

## 1. Set your token

Open your team repo on GitHub and find the issue "Your course MCP tokens". Copy the token next to your name. It is
yours only. Do not paste it into a file in any repo, a commit or a chat.

Put it in the environment variable `KB_MCP_TOKEN`. An environment variable is a named setting that one terminal window,
and the programs started from it, can read. Set it in the terminal you will use for the rest of the tutorial.
On Windows, use PowerShell, not Command Prompt (cmd.exe).
In each command below, replace all of `paste-your-token-here` with your token and keep the quotes around it.

macOS or Linux (zsh or bash):

```bash
export KB_MCP_TOKEN='paste-your-token-here'
```

Windows PowerShell:

```powershell
$env:KB_MCP_TOKEN = 'paste-your-token-here'
```

These commands print nothing. They set the token for this terminal window only.

You need the token in every new window if you start your assistant from an editor or an app icon (VS Code, the Kiro
app). Then make it permanent. On macOS, add the `export` line to `~/.zshrc` (`~/.bashrc` for bash on Linux). On
Windows, run `setx KB_MCP_TOKEN "paste-your-token-here"` once in PowerShell (double quotes here). This stores the token
in a file or setting on your laptop only. Never commit or share that file. Then close and reopen the terminal and the
editor.

Check it is set without showing it:

```bash
uv run python -c "import os; print('set' if os.environ.get('KB_MCP_TOKEN') else 'NOT set')"
```

You should see `set`.

## 2. Check your token with `mcp_check.py`

In the same terminal, go to the root folder of the tutorial repo, then into its `mcp` folder, and run the check:

```bash
cd mcp
uv run mcp_check.py
```

The first run downloads the Python packages, which takes a few seconds. You should see something like this:

```text
Connected to https://kb-cloud-students.fly.dev/mcp
Tools: get_kb_doc, list_kb_topics, query_kb
query_kb("S3 storage classes") first result: <a course file path>
  | <first line of that file>
  | <second line of that file>
OK: your token works and the course MCP server answered.
```

The last line must start with `OK:`. If you see a line starting `FAILED:` instead, it says what to fix. The three common ones are "KB_MCP_TOKEN is not
set" (go back to step 1 in this terminal), "the server refused your token (HTTP 401)" (copy the token again) and "could
not reach" or "no answer" (network or VPN). Ask a TA if the fix does not work.

## 3. Connect your assistant

Go to the root folder of your team repo (the folder that holds `docs/` and `.mcp.json.example`). Copy the example file.
It already names the course server and reads your token from `KB_MCP_TOKEN`, so you do not edit it.

| Assistant | macOS or Linux | Windows PowerShell |
|---|---|---|
| Claude Code | `cp .mcp.json.example .mcp.json` | `Copy-Item .mcp.json.example .mcp.json` |
| Kiro | `mkdir -p .kiro/settings && cp .mcp.json.example .kiro/settings/mcp.json` | `New-Item -ItemType Directory -Force .kiro\settings; Copy-Item .mcp.json.example .kiro\settings\mcp.json` |

Never put the token itself in `.mcp.json`. The file reads it from `KB_MCP_TOKEN`. `.mcp.json` is git-ignored, so it
stays on your laptop. Check: run `git status`. You should not see `.mcp.json` in the list. If you do, stop and ask a TA.

Start your assistant with the token set:

- Claude Code: in the terminal where you set the token, in the repo root, run `claude`. It asks once whether to use
  the servers in `.mcp.json`. Approve them.
- Kiro: make the token permanent (step 1), quit Kiro fully, then open Kiro again on the repo root folder.

Check the connection:

- Claude Code: type `/mcp`. You should see `436c` and `aws-knowledge` listed as connected.
- Kiro: open the MCP servers view in the Kiro panel. You should see `436c` and `aws-knowledge` with a connected status.

If `436c` is missing or failed, do not edit `.mcp.json`. Ask a TA.

## 4. Run two MCP tests

Ask your assistant each question below, one at a time. The answer is only in the course files, so a correct answer
needs a `query_kb` call.

Test 1: `Using only the course MCP, why does sorting a Parquet file by a column help queries that filter on that column? Name the course file you used.`
You should see an answer that names a course file whose path starts with `436c-student/` (for this question, a file about formats and layout) and quotes or paraphrases it.

Test 2: `Using only the course MCP, how does the course compare AWS Lambda with EC2 for cost? Name the course file you used.`
You should see an answer that names a course file whose path starts with `436c-student/` (for this question, a file about compute billing or Lambda) and says which lecture the fact is from: facts carry a tag such as `[L2]`.

To tell the assistant really called the tool, look in the chat for the tool call line. Claude Code shows it as
`436c - query_kb (MCP)` with the query it sent. Kiro shows the tool name and asks you to allow it. If you see no tool
call, the assistant answered from memory. Ask it again with "Use the query_kb tool and show me the file paths it
returned."

Check the file path is real. Ask: "Call get_kb_doc on that file path and show me its first three lines." A real path
returns the document. A made-up path returns an error or nothing.

## 5. Check your project proposal

Open `docs/proposal.md` in your team repo and check it has sections 1 to 7. If it is missing, ask a TA. Then paste
this prompt into your assistant:

```text
Read docs/proposal.md and the experiment files it links in section 6. Do not edit any file. Do not open .mcp.json.
List every number (rows, GB, time, money, counts) and every claim about how an AWS service works or what it costs.
For each one, search the course MCP server with query_kb. For a fact about an AWS service, also search the AWS
Knowledge MCP server. Then give me one table with these columns:
claim | where in the proposal (section number) | source found (course file path or AWS docs URL) | agrees / differs / not found
Put only sources you actually got from a tool call in the third column. If no tool result supports a claim,
write "not found". After the table, list the "differs" rows again with one sentence each on what the source says.
```

You should see `query_kb` tool calls in the chat, then a table with one row per claim and a short list of "differs"
rows. If every row says "not found" and you saw no tool calls, the tools did not run. Go back to step 3.

For each "differs" row, read the source yourself. Then either fix `docs/proposal.md`, or open an issue in your team
repo that quotes the claim, links the source and says why your proposal is right. A "not found" row is not an error.
It means the course files do not cover that claim, so check it in the AWS docs yourself.

## For TAs and the curious: test the check offline

`stand_in_server.py` is a small local copy of the course server with fake results, for tests only. Run the tests:

In the `mcp` folder, run:

```bash
uv run pytest -q
```

You should see that all tests passed.
