"""The whole run in one command (README steps 2, 3, 4, 6, 8 and 9): estimate, check, eval on the test cases, GEPA, eval again, comparison and cost.
Use it to catch up. In the tutorial, run the steps one by one (README) so you read the failures first.

    uv run python run_all.py
"""

from __future__ import annotations

import sys

import budget
import check_gateway
import compare
import gateway
import optimize


def run_eval(prompt: str) -> None:
    from inspect_ai import eval as inspect_eval

    from task import sql_cases

    logs = inspect_eval(sql_cases(split="test", prompt=prompt), log_dir=str(compare.LOGS), display="plain")
    if logs[0].status != "success":
        raise gateway.GatewayError(f"the eval with {prompt} did not finish: {logs[0].error.message if logs[0].error else logs[0].status}")


def main() -> int:
    budget.print_estimate()
    if check_gateway.main() != 0:
        return 1
    try:
        run_eval("prompt.txt")
        code = optimize.main([])
        if code != 0:
            return code
        run_eval("prompt.optimized.txt")
    except gateway.GatewayError as e:
        print(f"PROBLEM: {e}")
        return 1
    return compare.main()


if __name__ == "__main__":
    sys.exit(main())
