"""How your assistant uses the course MCP server, in about 20 lines: connect, list the tools, search, open a document.

    uv run python mcp_minimal.py

mcp_check.py does the same with checks and plain error messages. Your coding assistant makes these same calls.
"""
import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "https://kb-cloud-students.fly.dev/mcp"
HEADERS = {"Authorization": "Bearer " + os.environ["KB_MCP_TOKEN"]}  # your token, from the environment


async def main():
    async with streamablehttp_client(URL, headers=HEADERS) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()  # what MCP tells the assistant: each tool and its description
            print("tools:", [t.name for t in tools.tools])
            found = await session.call_tool("query_kb", {"query": "Parquet row groups", "k": 1})  # search
            print("query_kb:", found.content[0].text[:300])
            doc = await session.call_tool("get_kb_doc", {"file_path": "436c-student/facts-formats-layout.md"})  # open
            print("get_kb_doc:", doc.content[0].text[:300])


asyncio.run(main())
