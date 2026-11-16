"""Failures from the 2026-11-16 tutorial that the stand-in did not show at first (plans/2026-11-16-b5t1-test-spec.md)."""
import subprocess
import sys

from conftest import kit_env


def run_optimize(srv, kit_copy, tmp_path, **env):
    p = subprocess.run([sys.executable, "optimize.py", "--max-metric-calls", "12"], cwd=kit_copy, text=True,
                       capture_output=True, timeout=300, env=kit_env(srv, tmp_path, **env))
    cands = kit_copy / "logs" / "gepa-candidates.md"
    return p, cands.read_text(encoding="utf-8") if cands.exists() else ""


def test_thinking_reflector_gets_room_for_a_reply_with_default_settings(stand_in, kit_copy, tmp_path):
    """A thinking reflection model spent all of 4096 tokens on reasoning, so GEPA got empty replies and no new prompt.
    With the kit's default REFLECTOR_MAX_TOKENS, the stand-in's thinking reflector answers and GEPA proposes."""
    p, cands = run_optimize(stand_in, kit_copy, tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    assert stand_in.empty_replies == 0
    assert "## Candidate 1" in cands  # a proposal besides the starting prompt
    seed = (kit_copy / "prompt.txt").read_text(encoding="utf-8")
    assert (kit_copy / "prompt.optimized.txt").read_text(encoding="utf-8") != seed


def test_thinking_reflector_at_4096_tokens_replies_empty(stand_in, kit_copy, tmp_path):
    """Documents the failure: at REFLECTOR_MAX_TOKENS=4096 the reflection replies are empty and GEPA proposes nothing."""
    p, cands = run_optimize(stand_in, kit_copy, tmp_path, REFLECTOR_MAX_TOKENS="4096")
    assert stand_in.empty_replies > 0
    assert "empty or null" in p.stderr  # the line students saw in the tutorial
    assert "## Candidate 1" not in cands
