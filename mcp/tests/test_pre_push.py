"""A broken file was pushed because a pipe hid the failing test run (2026-11-16). tools/pre-push must stop the push
when either suite fails. Tested with a fake uv on PATH, never by running the real hook (it would run this suite)."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "tools" / "pre-push"


def run_hook(tmp_path, fail_in: str) -> subprocess.CompletedProcess:
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "uv").write_text(f'#!/bin/sh\necho "fake uv in $(basename "$PWD")"\n'
                             f'[ "$(basename "$PWD")" = "{fail_in}" ] && exit 1\nexit 0\n')
    (fake / "uv").chmod(0o755)
    env = dict(os.environ, PATH=f"{fake}{os.pathsep}{os.environ['PATH']}")
    return subprocess.run(["bash", str(HOOK)], cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)


def test_pre_push_stops_when_a_suite_fails(tmp_path):
    assert os.access(HOOK, os.X_OK)
    for suite in ("mcp", "evals-gepa"):
        (tmp_path / suite).mkdir()
        p = run_hook(tmp_path / suite, fail_in=suite)
        assert p.returncode != 0 and f"{suite} tests failed" in p.stderr


def test_pre_push_passes_when_both_suites_pass(tmp_path):
    p = run_hook(tmp_path, fail_in="none")
    assert p.returncode == 0 and p.stdout.splitlines() == ["fake uv in mcp", "fake uv in evals-gepa"]
