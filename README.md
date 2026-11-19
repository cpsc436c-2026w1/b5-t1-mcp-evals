# CPSC 436C B5T1: course MCP and prompt evaluation

Connect a coding assistant to the course MCP server and use the course knowledge base to check your project proposal. Then call
the course LLM gateway with the same token, evaluate a prompt on held-out cases with Inspect, read and name the
failures, let GEPA rewrite the prompt, evaluate again and price the session in CAD.

| Part | Folder |
|---|---|
| A: course MCP | [`mcp/`](mcp/README.md) |
| B: course LLM gateway and prompt evaluation | [`evals-gepa/`](evals-gepa/README.md) |

## Before the tutorial

Do these steps at home, so the tutorial time goes to the exercises.

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. In a terminal on your laptop, clone this tutorial repository:
   `git clone https://github.com/cpsc436c-2026w1/b5-t1-mcp-evals.git`. You should see the folders `mcp/` and
   `evals-gepa/` in it.
3. In a terminal on your laptop, clone your team repository. Check that it contains `docs/proposal.md`.
4. Install one coding assistant, following its official page for your operating system:
   - Claude Code: [Set up Claude Code](https://code.claude.com/docs/en/setup).
   - Kiro IDE: [Kiro installation](https://kiro.dev/docs/getting-started/installation/), IDE tab: download the
     installer from [kiro.dev](https://kiro.dev) and run it.
   - Kiro CLI: [Kiro installation](https://kiro.dev/docs/getting-started/installation/), CLI tab. On macOS or Linux,
     run this in a terminal:

     ```text
     curl -fsSL https://cli.kiro.dev/install | bash
     ```

     On Windows 11, run this in PowerShell:

     ```text
     irm 'https://cli.kiro.dev/install.ps1' | iex
     ```

5. Sign in to your assistant:
   - Claude Code: in a terminal, run `claude` and follow the sign-in prompt.
   - Kiro IDE: open Kiro and sign in with Google, GitHub or AWS Builder ID
     ([Kiro authentication](https://kiro.dev/docs/getting-started/authentication/)).
   - Kiro CLI: in a terminal, run `kiro-cli login` and sign in in your browser with Google, GitHub or AWS Builder ID
     ([Kiro authentication](https://kiro.dev/docs/getting-started/authentication/)). The Kiro CLI does nothing
     until you sign in: every command, including `kiro-cli mcp list`, stops with
     `You are not logged in, please log in with kiro-cli login`.
6. On GitHub, open the issue "Your course MCP tokens" in your team repository and copy the token next to your name.
7. Set `KB_MCP_TOKEN` as [part A, section 2](mcp/README.md#2-set-up-once) shows. If you will start your assistant
   from an app icon, such as the Kiro IDE, also make the setting permanent, as the same section shows.

## Start

Start with [part A](mcp/README.md), then continue to [part B](evals-gepa/README.md). See the
[course tutorials page](https://cpsc436c-2026w1.github.io/lecture-reviews/tutorials.html) for the other tutorials.
