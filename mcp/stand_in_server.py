"""Local stand-in for the course MCP server. For tests only.

Same three tool names and argument shapes as the course server, canned results,
streamable HTTP at http://127.0.0.1:<port>/mcp, bearer token checked against a test value.

Run:  uv run stand_in_server.py --port 8765
Then: KB_MCP_URL=http://127.0.0.1:8765/mcp KB_MCP_TOKEN=test-token uv run mcp_check.py
"""

import argparse

import uvicorn
from mcp.server.fastmcp import FastMCP

TEST_TOKEN = "test-token"

DOCS = {
    "decks/l05-storage.qmd": (
        "S3 storage classes trade retrieval speed for storage price.\n"
        "Standard-IA charges a minimum of 30 days per object.\n"
        "Glacier classes need a restore before you can read the object."
    ),
    "decks/l16-streaming.qmd": (
        "A stream is an unbounded sequence of records.\n"
        "Kinesis Data Streams keeps records in shards."
    ),
}

mcp = FastMCP("436c-stand-in", log_level="WARNING", stateless_http=True)


@mcp.tool()
def query_kb(query: str, domain: str | None = None, course: str | None = None, k: int = 8) -> dict:
    """BM25 search over the course corpus (canned)."""
    words = query.lower().split()
    hits = [
        {"file_path": path, "snippet": text[:1500]}
        for path, text in DOCS.items()
        if any(w in text.lower() for w in words)
    ]
    return {"results": hits[:k]}


@mcp.tool()
def get_kb_doc(file_path: str, domain: str | None = None) -> dict:
    """Full text of one document (canned)."""
    if file_path not in DOCS:
        return {"error": f"not found: {file_path}"}
    return {"file_path": file_path, "content": DOCS[file_path]}


@mcp.tool()
def list_kb_topics(domain: str | None = None) -> dict:
    """Indexed topics with file counts (canned)."""
    return {"topics": [{"topic": "storage", "files": 1}, {"topic": "streaming", "files": 1}]}


class BearerCheck:
    """ASGI middleware: answer 401 unless the Authorization header carries the test token."""

    def __init__(self, app, token: str):
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and dict(scope["headers"]).get(b"authorization") != self.expected:
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b'{"error":"invalid token"}'})
            return
        await self.app(scope, receive, send)


def build_app(token: str = TEST_TOKEN):
    return BearerCheck(mcp.streamable_http_app(), token)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--token", default=TEST_TOKEN)
    args = ap.parse_args()
    # The session manager starts in the Starlette lifespan, which the middleware passes through.
    uvicorn.run(build_app(args.token), host="127.0.0.1", port=args.port, log_level="warning")
