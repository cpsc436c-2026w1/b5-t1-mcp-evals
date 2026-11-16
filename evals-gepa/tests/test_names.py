"""Token and gateway names: KB_MCP_TOKEN is the course standard; L17's names still work."""
import gateway


def test_kb_mcp_token_wins_over_course_mcp_token(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("KB_MCP_TOKEN", "a")
    monkeypatch.setenv("COURSE_MCP_TOKEN", "b")
    assert gateway.token() == "a"


def test_course_mcp_token_alone_still_works(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("KB_MCP_TOKEN", raising=False)
    monkeypatch.setenv("COURSE_MCP_TOKEN", "b")
    assert gateway.token() == "b"


def test_l17_gateway_url_without_v1_gets_v1(monkeypatch):
    monkeypatch.delenv("COURSE_GATEWAY_URL", raising=False)
    monkeypatch.setenv("GATEWAY_URL", "https://example.test")
    assert gateway.base_url() == "https://example.test/v1"


def test_course_gateway_url_wins(monkeypatch):
    monkeypatch.setenv("COURSE_GATEWAY_URL", "https://a.test/v1")
    monkeypatch.setenv("GATEWAY_URL", "https://b.test")
    assert gateway.base_url() == "https://a.test/v1"
