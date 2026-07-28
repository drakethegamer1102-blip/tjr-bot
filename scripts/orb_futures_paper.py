"""ORB FUTURES — paper-trading simulator (MES proxied by SPY bars).

Alpaca has no futures, so this simulates the ORB FUTURES strategy on the S&P 500:
it pulls SPY 5-minute bars (a clean stand-in for the MES price series — MES tracks the
same index), runs the ORB FUTURES logic, simulates fills/stops/targets/EOD-flatten in a
local paper ledger, and sends the SAME Telegram alerts the live bot uses.

Nothing here touches a broker or real money. It writes a JSON ledger to
state/orb_futures_paper.json so results accumulate across runs.

Usage:
    python scripts/orb_futures_paper.py            # simulate the most recent session, alert
    python scripts/orb_futures_paper.py --days 30  # backfill/simulate the last N days
    python scripts/orb_futures_paper.py --no-telegram
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tjrbot.config import load_settings
from tjrbot.data.alpaca_data import get_stock_bars
from tjrbot.strategies import orb_futures
from tjrbot.strategies.orb_futures import contracts_for, MES_POINT_VALUE

try:
    from tjrbot.notify.telegram import TelegramNotifier
except Exception:  # notify optional
    TelegramNotifier = None  # type: ignore

PROXY_SYMBOL = "SPY"          # stands in for MES (both track the S&P 500)
# SPY trades at ~1/10 of the S&P 500 index (and thus ~1/10 of MES/ES, which quote the
# index directly). Scale SPY OHLC up by ~10 so entries/stops/targets land on the real MES
# price scale and the $5/point contract math produces representative dollar P&L. This is an
# approximation (SPY tracks total-return-adjusted price, not the exact index) but makes the
# paper economics realistic instead of ~7x too small.
PROXY_TO_INDEX = 10.0
# NOT under state/ (which is gitignored): this ledger is committed back by the GitHub
# Actions workflow so paper equity survives GitHub's stateless runs.
LEDGER = Path(__file__).resolve().parent.parent / "orb_futures_ledger.json"
START_EQUITY = 50_000.0       # a typical futures paper/eval account size


def _load_ledger() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except Exception:
            pass
    return {"equity": START_EQUITY, "trades": []}


def _save_ledger(led: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=2, default=str))


def _simulate_day(today, equity: float) -> list[dict]:
    """Return closed paper trades for one session (list of dicts)."""
    sigs = orb_futures.generate(today)
    results = []
    for s in sigs:
        n = contracts_for(equity, s.entry, s.stop, risk_fraction=0.01)
        if n < 1:
            continue
        # walk forward from the signal bar: stop / target / else EOD close
        fut = today.iloc[s.index + 1:]
        if fut.empty:
            continue
        exit_px = float(today["close"].iloc[-1])   # EOD default
        exit_kind = "eod"
        for _, b in fut.iterrows():
            if s.side == "long":
                if b.low <= s.stop:
                    exit_px, exit_kind = s.stop, "stop"; break
                if b.high >= s.target:
                    exit_px, exit_kind = s.target, "target"; break
            else:
                if b.high >= s.stop:
                    exit_px, exit_kind = s.stop, "stop"; break
                if b.low <= s.target:
                    exit_px, exit_kind = s.target, "target"; break
        points = (exit_px - s.entry) if s.side == "long" else (s.entry - exit_px)
        pnl = points * MES_POINT_VALUE * n
        results.append({
            "day": str(today.index[-1].date()),
            "side": s.side, "contracts": n,
            "entry": round(s.entry, 2), "stop": round(s.stop, 2),
            "target": round(s.target, 2), "exit": round(exit_px, 2),
            "exit_kind": exit_kind, "points": round(points, 2), "pnl": round(pnl, 2),
        })
    return results


def main(argv: list[str]) -> int:
    days = 1
    if "--days" in argv:
        days = int(argv[argv.index("--days") + 1])
    send = "--no-telegram" not in argv

    s = load_settings()
    bars = get_stock_bars(s.alpaca_key, s.alpaca_secret, PROXY_SYMBOL, "5Min", max(days + 2, 3))
    if bars.empty:
        print("no bars returned"); return 1
    # scale SPY prices to the MES/S&P-500 index level (volume left as-is)
    for col in ("open", "high", "low", "close"):
        bars[col] = bars[col] * PROXY_TO_INDEX

    led = _load_ledger()
    seen_days = {t["day"] for t in led["trades"]}
    sessions = sorted(bars.groupby(bars.index.date), key=lambda kv: kv[0])
    sessions = sessions[-days:]

    new_trades = []
    for _day, today in sessions:
        today = today.between_time("09:30", "16:00")
        if len(today) < 6:
            continue
        day_str = str(today.index[-1].date())
        if day_str in seen_days:      # don't double-count a day already simulated
            continue
        for t in _simulate_day(today, led["equity"]):
            led["equity"] += t["pnl"]
            led["trades"].append(t)
            new_trades.append(t)

    _save_ledger(led)

    # ---- report ----
    tot = sum(t["pnl"] for t in led["trades"])
    n = len(led["trades"])
    wins = sum(1 for t in led["trades"] if t["pnl"] > 0)
    wr = (wins / n * 100) if n else 0
    header = (f"ORB FUTURES (paper, MES via SPY) — equity ${led['equity']:,.0f}\n"
              f"lifetime: {n} trades · win {wr:.0f}% · net ${tot:+,.0f}")
    if new_trades:
        lines = [f"  {t['side'].upper()} {t['contracts']}x @ {t['entry']} "
                 f"-> {t['exit']} ({t['exit_kind']})  ${t['pnl']:+,.0f}" for t in new_trades]
        body = header + "\n" + f"new today ({len(new_trades)}):\n" + "\n".join(lines)
    else:
        body = header + "\nno new ORB FUTURES trades this run."
    print(body)

    if send and TelegramNotifier and s.telegram_token:
        TelegramNotifier(s.telegram_token, s.telegram_chat_id).send("🔮 " + body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
