"""Choosing the models and the key: GEPA_REFLECTOR, TASK_MODEL, LLM_API_KEY; GPT models and temperature."""

import openai
import pytest
from inspect_ai import eval as inspect_eval

import budget
import check_gateway
import gateway
import optimize
import stand_in_gateway
from task import sql_cases


def score(log) -> float:
    return next(s for s in log.results.scores if s.name == "sql_check").metrics["accuracy"].value


def test_stand_in_refuses_temperature_0_for_gpt_like_the_provider(stand_in):
    c = openai.OpenAI(base_url=gateway.base_url(), api_key=stand_in_gateway.TOKEN, max_retries=0)
    with pytest.raises(openai.BadRequestError) as e:
        c.chat.completions.create(model="gpt-6-luna", messages=[{"role": "user", "content": "hi"}], temperature=0)
    assert e.value.status_code == 400 and "temperature" in str(e.value)


def test_temperature_0_for_qwen_only():
    assert gateway.sampling("qwen3.8-27b", 10) == {"temperature": 0, "max_tokens": 10}
    assert gateway.sampling("gpt-6-luna", 10) == {"max_tokens": 10}


def test_gpt_on_openai_gets_max_completion_tokens(monkeypatch):
    monkeypatch.setenv("COURSE_GATEWAY_URL", "https://api.openai.com/v1")
    assert gateway.sampling("gpt-6-luna", 10) == {"max_completion_tokens": 10}
    assert gateway.sampling("qwen3.8-27b", 10) == {"temperature": 0, "max_tokens": 10}


def test_luna_reflection_end_to_end(stand_in, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEPA_REFLECTOR", "gpt-6-luna")
    out = tmp_path / "prompt.luna.txt"
    assert optimize.main(["--max-metric-calls", "12", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "reflection gpt-6-luna" in printed and "'reflect':" in printed
    assert stand_in.calls_by_model.get("gpt-6-luna", 0) >= 1
    assert "qwen3.8-27b" not in stand_in.calls_by_model
    for r in stand_in.requests:
        assert ("temperature" in r) == (r["model"] != "gpt-6-luna")
    spent = float(printed.split("cost ")[-1].split(" CAD")[0])
    assert spent > 0  # luna has a course price
    before = inspect_eval(sql_cases(split="test", prompt="prompt.txt"), log_dir=str(tmp_path), display="none")[0]
    after = inspect_eval(sql_cases(split="test", prompt=str(out)), log_dir=str(tmp_path), display="none")[0]
    assert after.status == "success" and score(after) >= score(before)


def test_budget_uses_the_chosen_reflection_model(monkeypatch):
    monkeypatch.delenv("GEPA_REFLECTOR", raising=False)
    monkeypatch.delenv("TASK_MODEL", raising=False)
    qwen = budget.estimate()
    monkeypatch.setenv("GEPA_REFLECTOR", "gpt-6-luna")
    luna = budget.estimate()
    assert luna["calls"]["gepa_reflect"] == qwen["calls"]["gepa_reflect"]
    assert luna["cost_cad"]["gepa_reflect"] > qwen["cost_cad"]["gepa_reflect"]
    assert luna["total_cad"] < budget.RUN_LIMIT_CAD


def test_luna_not_on_this_key_gives_a_plain_403(stand_in, monkeypatch, capsys):
    stand_in.models.remove("gpt-6-luna")
    monkeypatch.setenv("TASK_MODEL", "gpt-6-luna")
    assert check_gateway.main() == 1
    out = capsys.readouterr().out
    assert "403: your key may not use gpt-6-luna now" in out


def test_llm_api_key_overrides_kb_mcp_token(stand_in, monkeypatch, capsys):
    monkeypatch.setenv("KB_MCP_TOKEN", "not-my-token")
    monkeypatch.setenv("LLM_API_KEY", stand_in_gateway.TOKEN)
    assert check_gateway.main() == 0
    out = capsys.readouterr().out
    assert "LLM_API_KEY is set" in out and stand_in_gateway.TOKEN not in out


def test_wrong_llm_api_key_names_that_variable(stand_in, monkeypatch, capsys):
    monkeypatch.setenv("LLM_API_KEY", "not-my-key")
    assert check_gateway.main() == 1
    assert "401" in (out := capsys.readouterr().out) and "LLM_API_KEY" in out and "not-my-key" not in out


def test_unknown_model_prints_cost_unknown_and_runs(stand_in, monkeypatch, tmp_path, capsys):
    stand_in.models += ["other-task-model", "other-reflector"]
    monkeypatch.setenv("TASK_MODEL", "other-task-model")
    monkeypatch.setenv("GEPA_REFLECTOR", "other-reflector")
    monkeypatch.setattr(gateway, "_warned", set())
    out = tmp_path / "prompt.other.txt"
    assert optimize.main(["--max-metric-calls", "12", "--out", str(out), "--budget-cad", "0.0001"]) == 0
    printed = capsys.readouterr()
    assert "cost unknown for other-task-model: not a course gateway price" in printed.out
    assert "cost unknown for other-reflector: not a course gateway price" in printed.out
    assert "WARNING: the cost meter does not count" in printed.out
    assert stand_in.calls_by_model.get("other-reflector", 0) >= 1 and out.read_text().strip()
    log = inspect_eval(sql_cases(split="test", prompt=str(out)), log_dir=str(tmp_path), display="none")[0]
    assert log.status == "success" and log.results.completed_samples == 12


def test_gpt_task_model_eval_runs_through_inspect(stand_in, monkeypatch, tmp_path):
    monkeypatch.setenv("TASK_MODEL", "gpt-6-luna")
    log = inspect_eval(sql_cases(split="test", prompt="prompt.txt"), log_dir=str(tmp_path), display="none")[0]
    assert log.status == "success" and log.results.completed_samples == 12
    assert all("temperature" not in r for r in stand_in.requests)
