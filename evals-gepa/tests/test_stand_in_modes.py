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


def test_gepa_minimal_runs_on_chat_completions_only(stand_in, kit_copy, tmp_path):
    """dspy.LM's default called /v1/responses, which the course gateway does not serve (404). gepa_minimal.py, as
    written, runs GEPA end to end on a gateway that serves chat completions only, and its reflection model gets room
    for a reply."""
    p = subprocess.run([sys.executable, "gepa_minimal.py"], cwd=kit_copy, text=True, capture_output=True, timeout=300,
                       env=kit_env(stand_in, tmp_path))
    assert p.returncode == 0, p.stderr[-2000:]
    assert stand_in.post_paths and all(x.endswith("/chat/completions") for x in stand_in.post_paths)
    assert stand_in.calls_by_model.get("qwen3.8-27b", 0) > 0 and stand_in.empty_replies == 0
    out = (kit_copy / "prompt.minimal.txt").read_text(encoding="utf-8")
    assert out.strip() and out != (kit_copy / "prompt.txt").read_text(encoding="utf-8")


def test_dspy_lm_without_model_type_chat_hits_responses_and_404s(stand_in):
    """Why model_type="chat" is in gepa_minimal.py: without it, dspy.LM posts to /v1/responses."""
    import dspy
    import pytest

    lm = dspy.LM("openai/qwen3.6-35b-a3b", api_base=f"http://127.0.0.1:{stand_in.server_address[1]}/v1",
                 api_key="stand-in-token", cache=False, num_retries=0)
    with pytest.raises(Exception, match="not found"):
        lm("hello")
    assert stand_in.post_paths == ["/v1/responses"]


GATEWAY_UPSTREAM_TIMEOUT_S = 60  # the course gateway's read timeout to the model (2026-11-16)


def test_slow_reply_is_not_cut_off_by_the_kit_client_timeout(stand_in):
    """A slow model reply must end at the gateway (502 after its upstream timeout), not at the kit's own client
    timeout. The stand-in delays its reply; the kit's client waits for it without a retry."""
    import gateway

    assert gateway.client().timeout > GATEWAY_UPSTREAM_TIMEOUT_S
    assert gateway.inspect_model().config.timeout > GATEWAY_UPSTREAM_TIMEOUT_S  # the Inspect eval's client too
    stand_in.delay_s = 1.0
    r = gateway.chat("qwen3.6-35b-a3b", [{"role": "user", "content": "hello"}], 64)
    assert r["text"] and stand_in.chat_calls == 1


def test_reply_slower_than_the_client_timeout_retries_then_says_so(stand_in, monkeypatch):
    """Control for the test above: with a client timeout shorter than the delay, the same reply times out, the kit
    retries and then stops with its plain timeout message."""
    import openai
    import pytest

    import gateway

    stand_in.delay_s = 1.0
    short = openai.OpenAI(base_url=gateway.base_url(), api_key=gateway.token(), max_retries=0, timeout=0.3)
    monkeypatch.setattr(gateway, "_client", short)
    monkeypatch.setattr(gateway, "_client_for", (gateway.base_url(), gateway.token()))
    with pytest.raises(gateway.GatewayError, match="took longer than"):
        gateway.chat("qwen3.6-35b-a3b", [{"role": "user", "content": "hello"}], 64)
    assert stand_in.chat_calls == gateway.RETRIES_502 + 1
