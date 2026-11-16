# B5T1 part A: connect to the course MCP server

**Goal.** When you ask your coding assistant about course material, or ask it to check your project proposal, the
answer should come from the course's own files, and you should be able to open the file an answer came from and see
that it says what the assistant claims. Without help, an assistant answers from what its model remembers, and you
cannot check where a statement came from.

**How MCP helps.** The course MCP server gives your assistant two tools on the course files: `query_kb` searches
them and returns passages with their file paths, and `get_kb_doc` opens one whole file by its path. In this part you
connect the server (Step 1), get answers that cite course files (Step 2), open the file behind an answer to check it
(Step 3), and check the numbers and AWS claims in your proposal against the course files and the AWS docs (Step 4).

L17 introduced MCP (Model Context Protocol), a standard way for an AI app to use tools, data and prompt templates
offered by another program. The course server searches lecture decks, tutorials and readings, and returns passages
with their file paths. Your coding assistant is the host app: it runs tool calls against the server and receives
tool results.

> ⚠️ **Where commands run.** In a terminal on your laptop, use the tutorial repo's `mcp` folder for the check.
> In a terminal on your laptop, use your team repo root to copy `.mcp.json.example`, run `git status`, and start Claude Code.
> In your assistant's chat, enter the test questions and the proposal prompt.

## 1. Before you start

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you have not already.
2. Clone your team repository. Check that it contains `docs/proposal.md` and `.mcp.json.example`.
3. Have Claude Code or Kiro available on your laptop.
4. Open your team repository on GitHub and find the issue "Your course MCP tokens". Copy the token next to your
   name. The token is yours only. Keep it out of team-repo files, commits and chats; section 2 shows the one local setting
   that holds it.

## 2. Set up (once)

An environment variable is a named setting that a terminal and the programs started from it can read. Set
`KB_MCP_TOKEN` in the terminal you will use for the tutorial. On Windows, use PowerShell, not Command Prompt
(`cmd.exe`). Replace all of `paste-your-token-here` with your token and keep the quotes.

macOS or Linux (zsh or bash):

```bash
export KB_MCP_TOKEN='paste-your-token-here'
```

Windows PowerShell:

```powershell
$env:KB_MCP_TOKEN = 'paste-your-token-here'
```

The commands do not print the token. The setting lasts for the current terminal window. The same token is the API
key for the course LLM gateway in part B.

**Or, for the scripts only: a `.env` file.** In your editor, create a file named `.env` in the tutorial repo root
(the folder that contains `mcp/` and `evals-gepa/`) with one line:

```text
KB_MCP_TOKEN=paste-your-token-here
```

Git ignores this file. `mcp_check.py` and every script in part B read it when the variable is not set. Your coding
assistant does not read it: for Step 1 you still need the environment variable above.

If you start your assistant from an editor or app icon, such as VS Code or the Kiro app, make the token setting
permanent. An app started from an icon does not read the settings of a terminal window.

- On macOS, open `~/.zshrc` in your editor and add the `export` line above. On Linux with bash, open
  `~/.bashrc` in your editor and add the line.
- On Windows, run the following once in PowerShell. Replace `paste-your-token-here` with your token and keep the
  double quotes:

  ```powershell
  setx KB_MCP_TOKEN "paste-your-token-here"
  ```

The setting is stored on your laptop only. Do not commit or share the file or the token. Close and reopen your
terminal and editor so they read the setting. If the editor still does not see the token, quit the editor. In a
terminal where the token is set, start the editor again. For VS Code, run `code .` in your team repo root.

In the terminal where you set the token, go to the tutorial repo root, the folder that contains `mcp/`. You should see that folder. From there, run:

```bash
cd mcp
uv run mcp_check.py
```

The first run downloads Python packages. On success, you should see:

```text
✓ KB_MCP_TOKEN is set
✓ connected to https://kb-cloud-students.fly.dev/mcp
✓ tools: get_kb_doc, list_kb_topics, query_kb
✓ query_kb("S3 storage classes") first result: <a course file path>
  | <first line of that file>
  | <second line of that file>
OK: your token works and the course MCP server answered.
```

The path and file lines depend on the search result. If a line in the terminal starts with `FAILED:`, read its fix
in the list below:

- `KB_MCP_TOKEN is not set`: set the token again in the same terminal.
- `the server refused your token (HTTP 401)`: copy the newest token from "Your course MCP tokens" and set it again
  in the terminal. Check the token in the terminal for extra spaces.
- `could not reach` or `no answer`: check your internet connection on your laptop. Try without your VPN or ask a TA
  about a work network or proxy.

In the terminal in the `mcp` folder, run the check again. Ask a TA if the fix does not work.

## 3. Steps

Each step has a prediction to write down in your notes first. Do the actions. At the end of the step, open the
**Check your predictions** box and compare it with the prediction in your notes.

### Step 1: connect your assistant

<details>
<summary>What happens when you do this step</summary>

**Goal:** You connect your assistant to the course MCP server, so it can search and open the course files instead of answering from memory.

```text
assistant  --reads configuration-->  MCP servers
           --tool calls----------->  course MCP server
```

When your assistant starts, it reads the configuration file, connects to each server the file names, and asks
each server for its list of tools.

</details>

1. In your editor, open `.mcp.json.example` at the root of your team repository, the folder containing `docs/` and
   `.mcp.json.example`. Read the file: it names the servers your assistant will connect to and reads the token from
   `KB_MCP_TOKEN`. Do not edit the file.
2. **Predict:** In your notes, write down which servers you expect your assistant to list as connected. What do
   you expect the list to show for `436c` if the assistant starts in a window where the token is not set?
3. In a terminal on your laptop, go to the root of your team repository. Copy the example for your assistant with
   the command for your operating system:

   | Assistant | macOS or Linux | Windows PowerShell |
   |---|---|---|
   | Claude Code | `cp .mcp.json.example .mcp.json` | `Copy-Item .mcp.json.example .mcp.json` |
   | Kiro | `mkdir -p .kiro/settings && cp .mcp.json.example .kiro/settings/mcp.json` | `New-Item -ItemType Directory -Force .kiro\settings; Copy-Item .mcp.json.example .kiro\settings\mcp.json` |

   You should see the command finish without an error in the terminal, and the copied file in your editor's file
   list of the team repo. If your team repo has no `.mcp.json.example`, ask a TA. Do not write one from memory.

4. In the terminal at your team repo root, run `git status`. You should see that neither `.mcp.json` nor
   `.kiro/settings/mcp.json` appears in the terminal output; both must stay on your laptop. If either appears,
   stop and ask a TA. Never put the token in these files.
5. Start your assistant with the token set:

   - **Claude Code:** in the terminal where you set the token, at the team repo root, run `claude`. Approve the
     servers in `.mcp.json` when asked.
   - **Kiro:** make the token permanent (section 2). Quit Kiro fully. Open Kiro again on the team repo root.

6. Check the connection. In Claude Code, type `/mcp`. In Kiro, open the MCP servers view in the Kiro panel. You
   should see `436c` and `aws-knowledge` with connected status. If `436c` is missing or failed, do not edit
   `.mcp.json`; ask a TA.

<details>
<summary>Check your predictions</summary>

The server view shows both `436c` and `aws-knowledge` connected. Without the token, `436c` shows as failed, because
the server refuses a call that does not carry a token. L17 described a host app running one MCP
client per server: the configuration tells your assistant which servers to connect to, and each permitted client
can list and call the server's tools.
</details>

### Step 2: ask about course material

<details>
<summary>What happens when you do this step</summary>

**Goal:** You ask about course material and watch the assistant search the course files, so its answer names the file it came from.

```text
user message  -->  assistant  --query_kb-->  course files
                              <--tool result--  paths and passages
```

The assistant decides whether to call a tool. When it calls `query_kb`, the course server searches the course
files and returns file paths and passages, and the assistant writes its reply from them.

</details>

1. **Predict:** using the tool list on the `✓ tools:` line the setup check printed in the terminal in the `mcp`
   folder, write down for each question whether the assistant will call a tool, and what kind of course file it will
   name.
2. In your assistant's chat, ask each question separately:

   > Using only the course MCP, why does sorting a Parquet file by a column help queries that filter on that column? Name the course file you used.

   > Using only the course MCP, how does AWS Lambda bill a function, and what do you pay between calls? Name the course file you used.

   You should see a reply to each question in the chat.
3. Look for the tool call in the chat. Claude Code shows `436c - query_kb (MCP)` with the query it sent. Kiro shows
   the tool name and asks you to allow it. You should see replies that name course files and quote or paraphrase
   their passages.
4. If you do not see a tool call in the chat, the assistant answered from memory. Ask again in the chat: "Use the
   query_kb tool and show me the file paths it returned." You should see a tool call and the returned file paths
   in the chat.

<details>
<summary>Check your predictions</summary>

Each question leads to at least one `query_kb` call, and each reply names a file whose path starts with
`436c-student/`. The Parquet question names a file about formats and layout, such as `facts-formats-layout.md`. The
Lambda question names a file about Lambda or compute billing, such as `facts-lambda-serverless.md` or
`facts-compute-billing.md`, and a fact it quotes ends with a lecture tag such as `[L2]`. If the reply is about other
services' prices only, ask: "Search again with query_kb for Lambda per-request billing."

L15 defined a tool call as a reply that names a tool and its arguments instead of answering the user.
The coding assistant runs the call and sends the tool result back, so the model can use the returned passages in
its reply.
</details>

### Step 3: open the file behind an answer

<details>
<summary>What happens when you do this step</summary>

**Goal:** You open the file behind an answer and check that it says what the assistant claimed. A path the server does not have returns nothing, so a file you can open really exists.

```text
assistant  --get_kb_doc(path)-->  course MCP server
           <--the whole file, or nothing--
```

</details>

1. In your notes, copy one file path and one sentence the assistant quoted or paraphrased from it in Step 2.
2. **Predict:** in your notes, write down whether you expect that file to contain the sentence, and what you expect
   the tool to return for a path that does not exist.
3. In your assistant's chat, ask (put in your path):

   ```text
   Use get_kb_doc to open <the path from Step 2>.
   Show me the paragraph that contains the sentence you quoted.
   ```

   You should see a `get_kb_doc` tool call and a paragraph from that file in the chat.
4. In your notes, mark whether the file says what the assistant claimed in Step 2.
5. In your assistant's chat, ask:

   ```text
   Use get_kb_doc to open 436c-student/facts-made-up.md.
   Tell me exactly what the tool returned.
   ```

   You should see the tool call return nothing: no file and no text.

<details>
<summary>Check your predictions</summary>

The real path returns the whole file, and the paragraph you asked for is in it. If the assistant's sentence is not
in the file, the assistant added it: check claims against the file, not against the reply. The made-up path returns
nothing, because the server only returns files it has. L17's MCP server exposes `get_kb_doc` as a tool, so you can
check a cited path yourself instead of trusting the reply.
</details>

### Step 4: check your project proposal

<details>
<summary>What happens when you do this step</summary>

**Goal:** You use the course files and the AWS docs to check the numbers and AWS claims in your proposal, so you can fix a wrong fact before staff feedback.

```text
proposal claims  -->  assistant  --query_kb-->  course files
                                --AWS Knowledge-->  AWS docs
                                <--tool results--  sources
                 <--  claim table and differing claims
```

The assistant reads your proposal, searches the course files and the AWS docs for each claim, and compares
them. It reports what the tools returned; you decide what to change in your proposal.

</details>

1. In your editor, open `docs/proposal.md` in your team repo and read sections 1 to 7, including the claims about
   AWS services and costs. You should see those sections in the editor. If the file is missing, ask a TA.
2. Before sending the prompt, write down in your notes which AWS claims in your proposal you expect the course files to cover
   and which you expect only the AWS docs to cover.
3. In your assistant's chat, give your assistant the following user message:

   ```text
   Read docs/proposal.md and the experiment files it links in section 6.
   Do not edit any file. Do not open .mcp.json.

   1. Fetch 436c-student/index.md, resources.md and prices.md with get_kb_doc.
   2. List every number (rows, GB, time, money, counts)
      and every claim about how an AWS service works or what it costs.
   3. For each claim, search the course MCP server with query_kb
      (domain "ops", course "436c").
      For a fact about an AWS service, also search the AWS Knowledge MCP server.
   4. Give me one table with these columns:
      claim | section | source found (course file path or AWS docs URL) | verdict
      Verdict is one of: agrees / agrees if … / differs / ours / not found.
      - "ours": a number the team measured or estimated itself;
        check only that it is consistent with the other numbers.
      - "agrees if …": the source adds a condition the proposal does not state.
      - Put only sources you actually got from a tool call in the third column.
        If no tool result supports a claim, write "not found".
   5. After the table, list the "differs" rows again,
      with one sentence each on what the source says.
   6. Then list any two places where the proposal gives different numbers
      or times for the same thing, and any claim that breaks a limit
      in resources.md (Lambda concurrency, budget, Region).
   ```

   You should see a claim table in the chat. Use its source column in the next actions.

4. In your assistant's chat, look for `get_kb_doc` and `query_kb` tool calls, a table with one row per claim, and
   a short list of "differs" rows. You should see the tool calls, table and list in the chat. If every row
   says "not found" and you saw no tool calls, the tools did not run. Return to Step 1 and check the connection.
5. For each "differs" row in your assistant's chat, read the source yourself. For a course file, ask the assistant
   to retrieve the file through `get_kb_doc` and read the file in the chat. For an AWS docs URL, open and read the
   page in a browser tab. You should see the course file in the chat or the AWS page in the browser tab. Fix
   `docs/proposal.md` in your editor, or open an issue on GitHub in your team repository that quotes the claim,
   links the source and says why your proposal is right. For a "not found" AWS-service row in the chat, read the
   AWS page in a browser tab. The tool results do not support that row. A row marked "ours" does not need a source;
   say in `docs/proposal.md` in your editor how you measured it.

<details>
<summary>Check your predictions</summary>

Most of your section 4 numbers are your own measurements, which the course files cannot check, so those rows say
"ours". A "not found" row is often one of them: check the number in `docs/proposal.md`. For DynamoDB, SQS and other
services the course files do not cover, the AWS Knowledge rows are the check.

Compare the "ours", "not found" and "differs" rows with the kinds of claim you predicted. Your own dataset numbers
are "ours", and your proposal may have zero "differs" rows. A tool result supplies a source for you to inspect, while the assistant's comparison still needs
your review. L17 recommends MCP tool calls with audit logs. The course server logs calls by each student's named
key.
</details>

## 4. Extra exercises

1. **Predict:** In your notes, write down whether you expect the assistant to call a tool if you ask the Parquet
   question from Step 2 without the words "Using only the course MCP".
2. In a new chat in your assistant, ask the question without those words. You should see a reply in the new chat.
3. Scroll the new chat and the Step 2 chat. Compare the tool call lines in both chats.

<details>
<summary>Check your prediction</summary>

Compare the tool call lines in both chats. The assistant may answer from memory without a tool call when the user
message does not ask it to use the course MCP. A file citation is easier to check when a tool result supplies it.
</details>

## 5. Clean up

Keep `.mcp.json`: the project uses it. The project uses your token until the end of term.

If you set a permanent token and later no longer want it, you can remove the permanent environment setting. If you
previously added a token line to a shell startup file, remove that line. On Windows, remove the `KB_MCP_TOKEN` user
environment variable in your environment settings.

## 6. Recap and reflection

<details>
<summary>What you did, why, and how the same work runs outside the tutorial (open after the tutorial)</summary>

- **You connected an assistant to MCP servers.** Configuration lets a host find servers. Projects can version
  server configuration for their assistants.
- **You searched course files.** `query_kb` supplied passages and paths. An assistant can use tool results to
  support a reply with sources.
- **You checked a path.** `get_kb_doc` let you inspect a cited document. Checking a source helps you find an
  invented or incorrect citation.
- **You reviewed proposal claims.** Course files and AWS docs gave you sources to compare with claims. You still
  decide whether to revise the proposal.
- **You used a named token.** The server permits clients with tokens and logs calls by key. Audit logs help
  operators review tool use outside the tutorial.

Reflection:

- When would you inspect a source yourself instead of relying on an assistant's comparison?
- What could you change in a user message if an assistant answers without the tool result you need?

</details>


## Files

| File | What it is |
|---|---|
| [`mcp_check.py`](mcp_check.py) | Checks the token, connection, tools and a course-file search. |
| [`stand_in_server.py`](stand_in_server.py) | Local stand-in server with fake results for tests. |
| [`tests/`](tests/) | Tests for the check. |
| [`pyproject.toml`](pyproject.toml) | Python project and dependency configuration. |

## For TAs and the curious

In the `mcp` folder, run the check's tests against [`stand_in_server.py`](stand_in_server.py):

```bash
uv run pytest -q
```

You should see that all tests passed.
