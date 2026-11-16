"""Check that your token reaches the CPSC 436C course MCP server.

Run:  uv run mcp_check.py
It reads your token from the environment variable KB_MCP_TOKEN and never prints it.
Exit code 0 means the server answered a real search.
"""

import json
import os
import sys

import anyio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from a .env file next to this script or in the repo root, for variables not already set.
    The file is git-ignored. Your coding assistant does not read it: for part A's assistant, set the variable."""
    from pathlib import Path as _P
    here = _P(__file__).resolve().parent
    for f in (here / ".env", here.parent / ".env"):
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip().removeprefix("export ").strip()
                    os.environ.setdefault(k, v.strip().strip('"').strip("'"))


_load_dotenv()

DEFAULT_URL = "https://kb-cloud-students.fly.dev/mcp"
TEST_QUERY = "S3 storage classes"
TIMEOUT_S = 30


class CheckError(Exception):
    """A failure with a plain message for the student."""


def fail(msg: str) -> None:
    print(f"FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def text_of(result) -> str:
    return "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")


async def preflight(url: str, token: str) -> None:
    """Send one plain HTTP request so a bad token or a network problem gives a clear message."""
    body = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "mcp_check", "version": "0.1"},
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            r = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as e:
        raise CheckError(
            f"could not reach {url} ({type(e).__name__}).\n"
            "Check your internet connection. On a VPN or a work network, try without it "
            "or ask a TA about the proxy."
        ) from e
    if r.status_code in (401, 403):
        raise CheckError(
            f"the server refused your token (HTTP {r.status_code}).\n"
            "Copy the token again from the issue 'Your course MCP tokens' in your team repo. "
            "Use the newest one, with no spaces or quotes around it."
        )
    if r.status_code >= 400:
        raise CheckError(f"the server answered HTTP {r.status_code}. Try again in a minute, then ask a TA.")


async def run(url: str, token: str) -> None:
    await preflight(url, token)
    http = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT_S)
    async with http:
        async with streamable_http_client(url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = sorted(t.name for t in tools.tools)
                print(f"✓ connected to {url}")
                print(f"✓ tools: {', '.join(names)}")
                if "query_kb" not in names:
                    raise CheckError("the server has no query_kb tool. Check the URL.")
                result = await session.call_tool("query_kb", {"query": TEST_QUERY, "k": 3})
                if result.isError:
                    raise CheckError(f"query_kb returned an error: {text_of(result)[:300]}")
                first = first_result(result)
                print(f'✓ query_kb("{TEST_QUERY}") first result: {first["file_path"]}')
                for line in first["lines"]:
                    print(f"  | {line}")


def find_hits(data) -> list[dict] | None:
    """Find the list of hits in a JSON result, whatever key wraps it."""
    if isinstance(data, list):
        return data if data and all(isinstance(h, dict) for h in data) else None
    if isinstance(data, dict):
        for key in ("results", "result", "hits", "items"):
            if key in data:
                found = find_hits(data[key])
                if found:
                    return found
    return None


def first_result(result) -> dict:
    """Return the first hit's file path and two non-empty lines of its snippet."""
    hits = find_hits(result.structuredContent)
    if hits is None:
        try:
            hits = find_hits(json.loads(text_of(result)))
        except ValueError:
            hits = None
    if hits:
        hit = hits[0]
        path = hit.get("file_path") or hit.get("path") or "(no path)"
        snippet = hit.get("snippet") or hit.get("content") or hit.get("text") or ""
    else:
        # Plain-text result: take the first line that looks like a path, then the lines after it.
        text = text_of(result)
        if not text.strip():
            raise CheckError("query_kb returned no results.")
        lines = text.splitlines()
        idx = next((i for i, l in enumerate(lines) if "/" in l or l.strip().endswith(".md")), 0)
        path = lines[idx].strip()
        snippet = "\n".join(lines[idx + 1 :])
    lines = [l.strip() for l in snippet.splitlines() if l.strip()][:2]
    return {"file_path": path, "lines": lines}


def unwrap(e: BaseException) -> BaseException:
    """Find the first real error inside the exception groups the transport raises."""
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    return e


def main() -> None:
    token = os.environ.get("KB_MCP_TOKEN", "").strip()
    if not token:
        fail(
            "KB_MCP_TOKEN is not set in this terminal.\n"
            "Set it (README section 2, Set up) in the same terminal, then run this again."
        )
    print("✓ KB_MCP_TOKEN is set")
    url = os.environ.get("KB_MCP_URL", DEFAULT_URL)
    async def run_with_timeout() -> None:
        with anyio.fail_after(TIMEOUT_S * 2):
            await run(url, token)

    try:
        anyio.run(run_with_timeout)
    except Exception as e:  # noqa: BLE001
        err = unwrap(e)
        if isinstance(err, CheckError):
            fail(str(err))
        if isinstance(err, TimeoutError):
            fail(f"no answer from {url} within {TIMEOUT_S * 2} seconds. Check your network, then ask a TA.")
        fail(f"the MCP session broke ({type(err).__name__}). Run again. If it repeats, show this to a TA.")
    print("OK: your token works and the course MCP server answered.")


if __name__ == "__main__":
    main()
