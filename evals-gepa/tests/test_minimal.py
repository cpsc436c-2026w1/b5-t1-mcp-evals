"""gepa_minimal.py stays the plain, reusable version: plain dspy.LM, chat completions, one dspy.GEPA call."""
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "gepa_minimal.py").read_text(encoding="utf-8")


def test_minimal_compiles():
    compile(SRC, "gepa_minimal.py", "exec")


def test_minimal_uses_plain_dspy_and_the_chat_api():
    assert SRC.count('model_type="chat"') == 2  # the course LLM gateway serves chat completions only
    assert "dspy.GEPA(" in SRC and "reflection_lm=" in SRC and "feedback=" in SRC
    for course_only in ("GatewayEngine", "GatewayLM", "Meter", "StopBeforeBudget", "budget"):
        assert course_only not in SRC


def test_minimal_is_short():
    code = [l for l in SRC.splitlines() if l.strip() and not l.strip().startswith("#")]
    assert len(code) <= 45
