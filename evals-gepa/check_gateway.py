"""Step 3: check that your token works. Lists the models your key may use, makes one tiny call, prints its cost.

    uv run python check_gateway.py
"""

from __future__ import annotations

import sys

import gateway


def main() -> int:
    print(f"gateway: {gateway.base_url()}")
    print("estimate: 1 call, at most 40 tokens in and 200 out, at most "
          f"{gateway.cad(gateway.WORKER, 40, 200):.6f} CAD")
    try:
        c = gateway.client()
        try:
            models = sorted(m.id for m in c.models.list().data)
        except Exception as e:  # noqa: BLE001  the plain message is enough here
            raise gateway.GatewayError(gateway.plain(e)) from None
        print("models your key may use:", ", ".join(models))
        r = gateway.chat(gateway.WORKER, [{"role": "user", "content": "Reply with the word ok."}], max_tokens=200)
    except gateway.GatewayError as e:
        print(f"PROBLEM: {e}")
        return 1
    print(f"reply from {gateway.WORKER}: {r['text'].strip()[:80]!r}")
    print(f"tokens: {r['tokens_in']} in, {r['tokens_out']} out. cost: {r['cad']:.6f} CAD")
    print("OK: the gateway works with your token.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
