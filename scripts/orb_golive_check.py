"""ORB go-live readiness tracker.

Answers ONE question: is ORB proven enough on paper to consider real money yet?

The user's plan (2026-07-27) is to prove ORB out on paper BEFORE any live/prop account.
The agreed bar is not just "is it profitable" — it's "is there enough evidence, across
GOOD and BAD market conditions, that the edge is real and not a lucky streak." This script
reads the live paper account's closed ORB trades and scores them against concrete gates.

Usage: python scripts/orb_golive_check.py [--telegram]
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone

from tjrbot.config import load_settings
from tjrbot.execution.alpaca_exec import Broker
from tjrbot.reconcile import compute_pnl

try:
    from tjrbot.notify.telegram import TelegramNotifier
except Exception:  # notify is optional for this read-only check
    TelegramNotifier = None  # type: ignore

# --- go-live gates (deliberately conservative; a paper edge overstates a live one) ---
MIN_TRADES = 50            # enough closed trades for the win% to mean something
MIN_LOSING_DAYS = 3        # must have survived real bad days, not only trending ones
MIN_PROFIT_FACTOR = 1.30   # gross win / gross loss; > 1.0 = profitable, 1.3 = a real cushion
MIN_WIN_RATE = 0.45        # a 2:1 R:R system stays green above ~40%; 45% = margin


def _orb_trades(orders):
    """Yield (pnl, closed_day) for every closed ORB round-trip in the order list."""
    for o in orders:
        coid = getattr(o, "client_order_id", "") or ""
        parts = coid.split("-")
        # ORB orders are tagged apx-orb-... (apex bot) — accept any prefix, strat must be 'orb'
        if len(parts) < 2 or parts[1] != "orb":
            continue
        entry = getattr(o, "filled_avg_price", None)
        if not entry:
            continue
        legs = getattr(o, "legs", None) or []
        ex = next((l for l in legs
                   if "filled" in str(getattr(l, "status", "")).lower()
                   and getattr(l, "filled_avg_price", None)), None)
        if ex is None:
            continue
        side = "long" if str(getattr(o, "side", "")).lower().endswith("buy") else "short"
        pnl = compute_pnl(side, float(entry), float(ex.filled_avg_price),
                         float(getattr(o, "filled_qty", 0) or 0))
        # closed day = the exit leg's fill time (fallback to entry time)
        when = getattr(ex, "filled_at", None) or getattr(o, "filled_at", None)
        day = str(when)[:10] if when else "?"
        yield pnl, day


def main(argv: list[str]) -> int:
    send = "--telegram" in argv
    s = load_settings()
    b = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)
    try:
        orders = b.closed_orders(limit=500)
    except Exception as e:  # noqa: BLE001
        print("fetch error:", e)
        return 1

    trades = list(_orb_trades(orders))
    n = len(trades)
    pnls = [p for p, _ in trades]
    wins = [p for p in pnls if p > 0]
    gross_win = sum(wins)
    gross_loss = -sum(p for p in pnls if p < 0)
    net = sum(pnls)
    win_rate = (len(wins) / n) if n else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)

    # per-day P&L -> how many distinct LOSING days (proxy for "survived bad conditions")
    by_day: dict[str, float] = defaultdict(float)
    for p, day in trades:
        by_day[day] += p
    losing_days = sum(1 for v in by_day.values() if v < 0)
    winning_days = sum(1 for v in by_day.values() if v > 0)

    mode = "PAPER" if s.alpaca_paper else "LIVE"
    pf_s = "inf" if pf == float("inf") else f"{pf:.2f}"

    def gate(ok: bool) -> str:
        return "PASS" if ok else "not yet"

    g_trades = n >= MIN_TRADES
    g_lose = losing_days >= MIN_LOSING_DAYS
    g_pf = pf >= MIN_PROFIT_FACTOR
    g_wr = win_rate >= MIN_WIN_RATE
    all_pass = g_trades and g_lose and g_pf and g_wr

    lines = [
        f"ORB go-live readiness  [{mode} account, {datetime.now(timezone.utc):%Y-%m-%d}]",
        f"  net ${net:+,.0f} · {n} trades · win {win_rate*100:.0f}% · PF {pf_s}",
        f"  days: {winning_days} winning / {losing_days} losing",
        "  ---- gates (all must PASS before considering real money) ----",
        f"  [{gate(g_trades)}] sample size   : {n}/{MIN_TRADES} trades",
        f"  [{gate(g_lose)}] bad-day proof  : {losing_days}/{MIN_LOSING_DAYS} losing days survived",
        f"  [{gate(g_pf)}] profit factor  : {pf_s} (need >= {MIN_PROFIT_FACTOR})",
        f"  [{gate(g_wr)}] win rate       : {win_rate*100:.0f}% (need >= {MIN_WIN_RATE*100:.0f}%)",
        "",
        ("  ==> READY to discuss live sizing (still start tiny)." if all_pass
         else "  ==> NOT READY. Keep running on paper. A hot streak is not proof."),
    ]
    report = "\n".join(lines)
    print(report)

    if send and TelegramNotifier and s.telegram_token:
        TelegramNotifier(s.telegram_token, s.telegram_chat_id).send("🩺 HEALTH · " + report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
