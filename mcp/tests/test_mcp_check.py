"""Run mcp_check.py against the local stand-in server: success, missing token, wrong token."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parent.parent
TEST_TOKEN = "test-token"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server_url():
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, str(KIT / "stand_in_server.py"), "--port", str(port), "--token", TEST_TOKEN],
        cwd=KIT,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            break
        except OSError:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("stand-in server did not start")
    yield f"http://127.0.0.1:{port}/mcp"
    proc.terminate()
    proc.wait(timeout=10)


def run_check(url: str | None, token: str | None):
    env = {k: v for k, v in os.environ.items() if k not in ("KB_MCP_TOKEN", "KB_MCP_URL")}
    env["NO_PROXY"] = "127.0.0.1,localhost"
    if url:
        env["KB_MCP_URL"] = url
    if token is not None:
        env["KB_MCP_TOKEN"] = token
    return subprocess.run(
        [sys.executable, str(KIT / "mcp_check.py")],
        cwd=KIT, env=env, capture_output=True, text=True, timeout=90,
    )


def test_success(server_url):
    r = run_check(server_url, TEST_TOKEN)
    assert r.returncode == 0, r.stderr
    assert "get_kb_doc, list_kb_topics, query_kb" in r.stdout
    assert "decks/l05-storage.qmd" in r.stdout
    assert "S3 storage classes trade retrieval speed" in r.stdout
    assert TEST_TOKEN not in r.stdout + r.stderr


def test_missing_token(server_url):
    r = run_check(server_url, None)
    assert r.returncode == 1
    assert "KB_MCP_TOKEN is not set" in r.stderr


def test_wrong_token(server_url):
    r = run_check(server_url, "old-token-123")
    assert r.returncode == 1
    assert "HTTP 401" in r.stderr
    assert "old-token-123" not in r.stdout + r.stderr


def test_network_failure():
    r = run_check(f"http://127.0.0.1:{free_port()}/mcp", TEST_TOKEN)
    assert r.returncode == 1
    assert "could not reach" in r.stderr


def test_first_result_plain_text():
    """The real server may answer in plain text instead of JSON; the parser copes."""
    sys.path.insert(0, str(KIT))
    from mcp.types import CallToolResult, TextContent

    import mcp_check

    res = CallToolResult(content=[TextContent(type="text", text="## decks/l05-storage.qmd\nline one\n\nline two\nline three")])
    first = mcp_check.first_result(res)
    assert "decks/l05-storage.qmd" in first["file_path"]
    assert first["lines"] == ["line one", "line two"]
