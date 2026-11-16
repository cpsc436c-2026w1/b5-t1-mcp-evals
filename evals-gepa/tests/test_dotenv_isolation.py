"""A .env file in the tutorial repo (a student's or a TA's real token) must not change what the tests see:
gateway.py reads .env when it is imported, so conftest.py sets B5T1_NO_DOTENV first."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROBE = ("import sys; sys.path[:0] = {path}; {first}import gateway, os; "
         "print(os.environ.get('KB_MCP_TOKEN'), gateway.base_url())")


def probe(kit: Path, with_conftest: bool) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("B5T1_NO_DOTENV", "KB_MCP_TOKEN", "COURSE_GATEWAY_URL")}
    code = PROBE.format(path=repr(["tests", "."]), first="import conftest; " if with_conftest else "")
    return subprocess.run([sys.executable, "-c", code], cwd=kit, env=env, text=True, capture_output=True,
                          timeout=120, check=True).stdout.strip()


def test_dotenv_in_the_repo_root_does_not_reach_the_tests(kit_copy):
    shutil.copytree(Path(__file__).resolve().parent, kit_copy / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    (kit_copy.parent / ".env").write_text("KB_MCP_TOKEN=from-dotenv\nCOURSE_GATEWAY_URL=http://dotenv.invalid/v1\n")
    assert probe(kit_copy, with_conftest=False) == "from-dotenv http://dotenv.invalid/v1"  # the kit reads it
    token, url = probe(kit_copy, with_conftest=True).split()
    assert token == "None" and "dotenv" not in url  # the tests do not
