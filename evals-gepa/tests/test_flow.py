from pathlib import Path

from inspect_ai import eval as inspect_eval

import optimize
from task import sql_cases


def score(log) -> float:
    return next(s for s in log.results.scores if s.name == "sql_check").metrics["accuracy"].value


def test_eval_runs_end_to_end(stand_in, tmp_path):
    log = inspect_eval(sql_cases(split="test", prompt="prompt.txt"), log_dir=str(tmp_path), display="none")[0]
    assert log.status == "success" and log.results.completed_samples == 12
    assert 0.0 < score(log) < 1.0  # some right, some wrong


def test_optimize_writes_a_prompt_and_after_is_at_least_before(stand_in, tmp_path):
    out = tmp_path / "prompt.optimized.txt"
    assert optimize.main(["--max-metric-calls", "12", "--out", str(out)]) == 0
    assert out.exists() and out.read_text().strip()
    cands = (Path(optimize.HERE) / "logs" / "gepa-candidates.md").read_text()
    assert "Candidate 0 (your starting prompt)" in cands and "(chosen)" in cands
    before = inspect_eval(sql_cases(split="test", prompt="prompt.txt"), log_dir=str(tmp_path), display="none")[0]
    after = inspect_eval(sql_cases(split="test", prompt=str(out)), log_dir=str(tmp_path), display="none")[0]
    assert score(after) >= score(before)


def test_cost_meter_stops_a_run_that_would_pass_the_budget(stand_in, tmp_path, capsys):
    out = tmp_path / "prompt.optimized.txt"
    assert optimize.main(["--budget-cad", "0.0001", "--out", str(out)]) == 3
    printed = capsys.readouterr().out
    assert "cost meter" in printed and "Stopped before the call" in printed
    spent = float(printed.split("cost ")[-1].split(" CAD")[0])
    assert spent <= 0.0001
    assert Path(out).exists()  # the best prompt seen so far is still written


def test_eval_retries_a_502(stand_in, tmp_path):
    stand_in.fail_502 = 1
    log = inspect_eval(sql_cases(split="test", prompt="prompt.txt"), log_dir=str(tmp_path), display="none")[0]
    assert log.status == "success" and log.results.completed_samples == 12
    assert stand_in.chat_calls == 13


def test_gateway_failure_during_gepa_stops_with_a_plain_message(stand_in, tmp_path, capsys):
    stand_in.fail_502 = 1000
    out = tmp_path / "prompt.optimized.txt"
    assert optimize.main(["--out", str(out)]) == 1
    printed = capsys.readouterr().out
    assert "PROBLEM: 502" in printed and "Run this step again" in printed
    assert not out.exists()
    assert stand_in.chat_calls < 60  # stopped early, not one refusal per case for the whole budget
