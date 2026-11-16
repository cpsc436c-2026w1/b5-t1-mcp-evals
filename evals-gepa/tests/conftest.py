import os
import shutil
import socket
from pathlib import Path

import pytest

os.environ["B5T1_NO_DOTENV"] = "1"  # before the kit is imported: gateway.py reads a .env file at import time

import gateway  # noqa: E402
import stand_in_gateway  # noqa: E402


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



SKIP = {".venv", "logs", ".env", "__pycache__", ".pytest_cache", "tests"}


@pytest.fixture
def kit_copy(tmp_path):
    """A copy of this folder without .venv, logs, .env or prompt.*.txt files except prompt.txt, so a run's logs and
    prompt files stay out of the repo. Run the kit in it with sys.executable, this folder's .venv Python."""
    here = Path(gateway.__file__).resolve().parent
    dst = tmp_path / "evals-gepa"
    shutil.copytree(here, dst, ignore=lambda d, names: [
        n for n in names if n in SKIP or (n.startswith("prompt.") and n != "prompt.txt")])
    return dst


def kit_env(srv, tmp_path, **extra) -> dict:
    """The environment a student has with the stand-in running: its URL and token, no .env file, an empty DSPy cache
    (a cached reply would pass without reaching the stand-in)."""
    drop = ("LLM_API_KEY", "TASK_MODEL", "GEPA_REFLECTOR", "REFLECTOR_MAX_TOKENS", "KB_MCP_TOKEN", "COURSE_GATEWAY_URL")
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(COURSE_GATEWAY_URL=f"http://127.0.0.1:{srv.server_address[1]}/v1", KB_MCP_TOKEN=stand_in_gateway.TOKEN,
               GATEWAY_BACKOFF_S="0.01", B5T1_NO_DOTENV="1", DSPY_CACHEDIR=str(tmp_path / "dspy-cache"),
               PYTHONUNBUFFERED="1")
    env.update(extra)
    return env
