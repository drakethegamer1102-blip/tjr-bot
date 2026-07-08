"""Per-strategy performance report from Alpaca's closed bot orders.

Groups every closed trade by the strategy that opened it (parsed from the order id)
and shows trades / win% / profit factor / net per strategy, plus the account total.
This is what the every-other-day review loop reads to decide what to keep, cut, or tune.

Usage: python scripts/strategy_report.py [--telegram]
"""

from __future__ import annotations

import sys
from collections import defaultdict

from tjrbot.config import load_settings
from tjrbot.execution.alpaca_exec import Broker
from tjrbot.notify.telegram import TelegramNotifier
from tjrbot.reconcile import compute_pnl


PREFIX_BOT = {"bot": "core", "apx": "apex", "rip": "riptide"}


def strategy_of(coid: str) -> str | None:
    if coid.startswith("tjr-"):  # legacy pre-multi-strategy orders
        return "core.tjr"
    parts = coid.split("-")
    if len(parts) > 1 and parts[0] in PREFIX_BOT:
        return f"{PREFIX_BOT[parts[0]]}.{parts[1]}"
    return None


def main(argv: list[str]) -> int:
    send = "--telegram" in argv
    s = load_settings()
    b = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)
    try:
        orders = b.closed_orders(limit=500)
    except Exception as e:  # noqa: BLE001
        print("fetch error:", e)
        return 1

    by: dict[str, list[float]] = defaultdict(list)
    for o in orders:
        coid = getattr(o, "client_order_id", "") or ""
        strat = strategy_of(coid)
        entry = getattr(o, "filled_avg_price", None)
        if not strat or not entry:
            continue
        legs = getattr(o, "legs", None) or []
        ex = next((l for l in legs if "filled" in str(getattr(l, "status", "")).lower()
                   and getattr(l, "filled_avg_price", None)), None)
        if ex is None:
            continue
        side = "long" if str(getattr(o, "side", "")).lower().endswith("buy") else "short"
        by[strat].append(compute_pnl(side, float(entry), float(ex.filled_avg_price),
                                     float(getattr(o, "filled_qty", 0) or 0)))

    acct = b.account()
    eq = float(acct.equity)
    le = float(acct.last_equity or eq)
    lines = [f"Strategy report — equity ${eq:,.0f} (today ${eq - le:+,.0f})"]
    if not by:
        lines.append("No closed trades yet.")
    for strat in sorted(by):
        pnls = by[strat]
        n = len(pnls)
        wins = [p for p in pnls if p > 0]
        gl = -sum(p for p in pnls if p < 0)
        gw = sum(wins)
        wr = (len(wins) / n * 100) if n else 0
        pf = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0)
        pf_s = "inf" if pf == float("inf") else f"{pf:.2f}"
        lines.append(f"  {strat}: {n} trades · win {wr:.0f}% · PF {pf_s} · net ${sum(pnls):+,.0f}")

    report = "\n".join(lines)
    print(report)
    if send and s.telegram_token:
        TelegramNotifier(s.telegram_token, s.telegram_chat_id).send("📊 " + report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
