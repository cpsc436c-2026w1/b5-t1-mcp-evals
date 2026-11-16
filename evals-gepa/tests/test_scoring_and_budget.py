import budget
import gateway
import pytest
import scoring

CASE = next(c for c in scoring.cases("train") if c["id"] == "t03")  # a percentage question


def test_reference_sql_passes_every_case():
    for c in scoring.cases():
        assert scoring.check(c["sql"], c)[0] == 1.0, c["id"]


def test_one_code_fence_is_accepted():
    assert scoring.check(f"```sql\n{CASE['sql']}\n```", CASE)[1] == "pass"


def test_text_after_the_query_is_refused():
    assert scoring.check(CASE["sql"] + "\n\nThis returns the share.", CASE)[1] == "not one SQL query"


def test_fraction_is_named_in_the_feedback():
    score, kind, feedback = scoring.check(CASE["sql"].replace("100.0 * ", "1.0 * "), CASE)
    assert (score, kind) == (0.0, "wrong value") and "fraction where a percentage" in feedback


def test_splits_do_not_overlap():
    ids = {s: {c["id"] for c in scoring.cases(s)} for s in ("train", "val", "test")}
    assert not (ids["train"] & ids["test"]) and not (ids["val"] & ids["test"]) and not (ids["train"] & ids["val"])


def test_one_run_is_under_the_course_limits():
    e = budget.estimate()
    assert e["total_cad"] < budget.RUN_LIMIT_CAD
    assert e["worst_seconds"] < 12 * 60
    assert e["total_calls"] < budget.RATE_PER_MIN


def test_meter_refuses_a_call_that_could_pass_the_budget():
    m = gateway.Meter(budget_cad=0.0001)
    msgs = [{"role": "user", "content": "x" * 300}]
    m.reserve(gateway.WORKER, msgs, 100)          # fits
    with pytest.raises(gateway.BudgetExceeded):
        m.reserve(gateway.REFLECTOR, msgs, 4096)  # could pass the budget: refused before the call
