# CPSC 436C B5T1: course MCP and prompt evaluation

Connect a coding assistant to the course MCP server and use course files to check your project proposal. Then call
the course LLM gateway with the same token, evaluate a prompt on held-out cases with Inspect, read and name the
failures, let GEPA rewrite the prompt, evaluate again and price the session in CAD.

| Part | Folder | Time |
|---|---|---|
| A: course MCP | [`mcp/`](mcp/README.md) | about 20 minutes |
| B: course LLM gateway and prompt evaluation | [`evals-gepa/`](evals-gepa/README.md) | about 30 minutes |

## Before you start

- Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Find your token in the issue "Your course MCP tokens" in your team repository.
- Clone your team repository and check that it contains `docs/proposal.md`.
- Have Claude Code or Kiro available.

## Start

Start with [part A](mcp/README.md), then continue to [part B](evals-gepa/README.md). See the
[course tutorials page](https://cpsc436c-2026w1.github.io/lecture-reviews/tutorials.html) for the other tutorials.
