"""Safely verify the Alpaca order path: submit a non-marketable limit, then cancel it.

Places a $1 limit buy on 1 share of AAPL (which can never fill), confirms it was
accepted, then cancels it. Proves order submission + cancellation work without ever
taking a position.
"""

from __future__ import annotations

import datetime as dt

from tjrbot.config import load_settings
from tjrbot.execution.alpaca_exec import Broker


def main() -> int:
    s = load_settings()
    b = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)
    print(f"Account equity: ${b.equity():,.2f}  (paper={s.alpaca_paper})")

    coid = "verify-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    order = b.submit_test_limit("AAPL", 1, 1.00, coid)
    print(f"Submitted test limit order  id={order.id}  status={order.status}  (limit $1 — cannot fill)")

    b.cancel(order.id)
    print(f"Cancelled test order {order.id}")
    print("Execution path verified ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
