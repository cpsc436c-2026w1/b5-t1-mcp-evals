"""Scoring by code: run the model's SQL in DuckDB on data/trips.csv and compare the first cell with the reference.

`check(reply, case)` returns (score, kind, feedback). `kind` is a coarse name from the checker. The finer name of
a failure (which rule the model broke) is for you to write in the error-analysis table (README step 5).
The eval (task.py) and the optimiser (optimize.py) both use this function, so they score the same way."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
_LOCK = threading.Lock()
_CON = None


def connect():
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute(f"CREATE TABLE trips AS SELECT * FROM read_csv_auto('{(DATA / 'trips.csv').as_posix()}')")
    return con


def cases(split: str | None = None) -> list[dict]:
    rows = [json.loads(line) for line in (DATA / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return [c for c in rows if split in (None, "all", c["split"])]


_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n(.*?)\n?```\s*$", re.S)


def extract_sql(reply: str) -> tuple[str | None, str | None]:
    """(sql, reason it is refused). One code fence around the query is accepted; any other text is not."""
    s = reply.strip()
    m = _FENCE.match(s)
    if m:
        s = m.group(1).strip()
    s = s.rstrip(";").strip()
    if not re.match(r"^(select|with)\b", s, re.I):
        return None, "the reply does not start with SELECT or WITH"
    if ";" in s or "\n\n" in s:
        return None, "the reply has more than one statement or text after the query"
    return s, None


def check(reply: str, case: dict) -> tuple[float, str, str]:
    global _CON
    head = f"Question: {case['question']}\nReference SQL: {case['sql']}\nReference value: {case['reference_value']}\n"
    sql, why = extract_sql(reply)
    if sql is None:
        return 0.0, "not one SQL query", head + f"FAILURE: not one SQL query ({why}). Model reply: {reply[:400]}"
    try:
        with _LOCK:
            if _CON is None:
                _CON = connect()
            row = _CON.execute(sql).fetchone()
    except Exception as e:
        return 0.0, "SQL error", head + f"FAILURE: SQL error. DuckDB said: {str(e)[:200]}\nModel SQL: {sql}"
    try:
        value = float(row[0])
    except (TypeError, ValueError, IndexError):
        return 0.0, "no number", head + f"FAILURE: the query did not return a number: {row}\nModel SQL: {sql}"
    ref = float(case["reference_value"])
    if abs(value - ref) <= case.get("tolerance", 0.01) * max(abs(ref), 1e-9):
        return 1.0, "pass", head + f"PASS. Model SQL: {sql}"
    hint = " It is 100 times too small: a fraction where a percentage was asked." if ref and abs(value * 100 - ref) <= 0.01 * abs(ref) else ""
    return 0.0, "wrong value", head + f"FAILURE: wrong value. The query returned {value:.4f}.{hint}\nModel SQL: {sql}"
