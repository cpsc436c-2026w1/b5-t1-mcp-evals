"""Writes data/trips.csv (300 made-up taxi trips, same seed every time) and the reference_value of every case in
data/cases.jsonl, by running each case's reference SQL in DuckDB. No model calls.

    uv run python data/build.py
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOROUGHS = ["Manhattan"] * 6 + ["Brooklyn"] * 2 + ["Queens"] * 2 + ["Bronx"]


def trips(n: int = 300, seed: int = 436) -> list[dict]:
    rng, start, rows = random.Random(seed), datetime(2024, 1, 1), []
    for i in range(1, n + 1):
        pick = start + timedelta(days=rng.randrange(31), hours=rng.randrange(24), minutes=rng.randrange(60))
        dist = round(rng.expovariate(1 / 3.0) + 0.2, 2)
        minutes = max(2, int(dist * rng.uniform(3, 6)))
        fare = round(3 + 2.5 * dist + 0.4 * minutes, 2)
        pay = rng.choices([2, 1, 3, 4], weights=[70, 24, 4, 2])[0]
        tip = round(fare * rng.choice([0, 0.1, 0.15, 0.2, 0.25]), 2) if pay == 2 else 0.0
        if rng.random() < 0.08:
            fare, tip = -fare, 0.0
        rows.append(dict(trip_id=i, pickup_datetime=pick.isoformat(sep=" "),
                         dropoff_datetime=(pick + timedelta(minutes=minutes)).isoformat(sep=" "),
                         passenger_count=rng.choices([1, 2, 3, 4, 5, 6], weights=[60, 20, 8, 6, 4, 2])[0],
                         trip_distance=dist, fare_amount=fare, tip_amount=tip, payment_type=pay,
                         pickup_borough=rng.choice(BOROUGHS)))
    return rows


def main() -> None:
    rows = trips()
    with (HERE / "trips.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from scoring import connect

    con = connect()
    path = HERE / "cases.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for c in cases:
        c["reference_value"] = round(float(con.execute(c["sql"]).fetchone()[0]), 4)
        print(c["split"], c["id"], c["reference_value"], c["question"])
    path.write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(HERE.parent))
    main()
