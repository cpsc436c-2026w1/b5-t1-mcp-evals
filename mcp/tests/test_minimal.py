"""mcp_minimal.py stays a short, plain MCP client."""
from pathlib import Path


def test_mcp_minimal_compiles_and_is_short():
    src = (Path(__file__).resolve().parent.parent / "mcp_minimal.py").read_text(encoding="utf-8")
    compile(src, "mcp_minimal.py", "exec")
    assert "list_tools" in src and "query_kb" in src and "get_kb_doc" in src
    assert len([l for l in src.splitlines() if l.strip() and not l.strip().startswith("#")]) <= 35
