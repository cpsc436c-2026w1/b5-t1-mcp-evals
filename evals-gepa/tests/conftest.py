import socket

import pytest

import gateway
import stand_in_gateway


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def stand_in(monkeypatch):
    """A fresh stand-in gateway on a free port, with the env vars a student would set."""
    port = free_port()
    srv = stand_in_gateway.serve(port)
    monkeypatch.setenv("COURSE_GATEWAY_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv("KB_MCP_TOKEN", stand_in_gateway.TOKEN)
    monkeypatch.setenv("GATEWAY_BACKOFF_S", "0.01")
    for v in ("LLM_API_KEY", "TASK_MODEL", "GEPA_REFLECTOR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(gateway, "_client", None)
    yield srv
    srv.shutdown()
    gateway._client = None
