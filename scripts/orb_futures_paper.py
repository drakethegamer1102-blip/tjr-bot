"""ORB FUTURES — intraday, multi-instrument paper simulator (prop-firm prep).

Alpaca has no futures, so this simulates ORB FUTURES on a basket of micro index futures,
each priced via a liquid ETF proxy scaled to the contract's index level (see
FUTURES_UNIVERSE in tjrbot/strategies/orb_futures.py):
    MES (S&P 500) via SPY, MNQ (Nasdaq) via QQQ, M2K (Russell) via IWM, MYM (Dow) via DIA.

Unlike the old once-a-day version, this scans the WHOLE session across ALL instruments —
the same breadth + intraday behaviour the live stock ORB has. That breadth is exactly why
the single-instrument version underperformed: on a day the S&P chops but the Nasdaq or
Russell trends, this now catches the trending one.

It keeps a JSON paper ledger (orb_futures_ledger.json at repo root, committed back by CI so
equity persists), and sends its OWN dedicated Telegram message — separate from the stock
bot's summary.

Usage:
    python scripts/orb_futures_paper.py                # simulate the latest session, alert
    python scripts/orb_futures_paper.py --days 30      # backfill last N sessions
    python scripts/orb_futures_paper.py --no-telegram
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tjrbot.config import load_settings
from tjrbot.data.alpaca_data import get_stock_bars
from tjrbot.strategies import orb_futures
from tjrbot.strategies.orb_futures import FUTURES_UNIVERSE, contracts_for

try:
    from tjrbot.notify.telegram import TelegramNotifier
except Exception:  # notify optional
    TelegramNotifier = None  # type: ignore

LEDGER = Path(__file__).resolve().parent.parent / "orb_futures_ledger.json"
START_EQUITY = 50_000.0        # typical futures paper/eval account size
RISK_FRACTION = 0.01           # 1% of equity risked per trade
MAX_CONCURRENT = 3             # never hold more than this many futures at once (prop-style)


def _load_ledger() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except Exception:
            pass
    return {"equity": START_EQUITY, "trades": []}


def _save_ledger(led: dict) -> None:
    LEDGER.write_text(json.dumps(led, indent=2, default=str))


def _proxy_bars(s, etf: str, days: int):
    """Return one ETF's 5-min bars for the requested lookback."""
    return get_stock_bars(s.alpaca_key, s.alpaca_secret, etf, "5Min", max(days + 2, 3))


def _simulate_session(sym: str, spec: dict, today, equity: float) -> list[dict]:
    """Simulate ORB FUTURES for ONE instrument on ONE session. Intraday walk-forward:
    the signal is detected at its bar, then filled/managed bar-by-bar (stop/target/EOD)."""
    scaled = today.copy()
    m = spec["proxy_mult"]
    for c in ("open", "high", "low", "close"):
        scaled[c] = scaled[c] * m

    sigs = orb_futures.generate(
        scaled, tick_size=spec["tick_size"], point_value=spec["point_value"],
    )
    out = []
    for sig in sigs:
        n = contracts_for(equity, sig.entry, sig.stop,
                          point_value=spec["point_value"], risk_fraction=RISK_FRACTION)
        if n < 1:
            continue
        fut = scaled.iloc[sig.index + 1:]
        if fut.empty:
            continue
        exit_px = float(scaled["close"].iloc[-1]); kind = "eod"
        for _, b in fut.iterrows():
            if sig.side == "long":
                if b.low <= sig.stop:  exit_px, kind = sig.stop, "stop"; break
                if b.high >= sig.target: exit_px, kind = sig.target, "target"; break
            else:
                if b.high >= sig.stop: exit_px, kind = sig.stop, "stop"; break
                if b.low <= sig.target: exit_px, kind = sig.target, "target"; break
        points = (exit_px - sig.entry) if sig.side == "long" else (sig.entry - exit_px)
        pnl = points * spec["point_value"] * n
        out.append({
            "day": str(today.index[-1].date()), "symbol": sym, "side": sig.side,
            "contracts": n, "entry": round(sig.entry, 2), "stop": round(sig.stop, 2),
            "target": round(sig.target, 2), "exit": round(exit_px, 2),
            "exit_kind": kind, "points": round(points, 2), "pnl": round(pnl, 2),
            "entry_ts": str(scaled.index[sig.index]),   # for concurrency ordering
        })
    return out


def main(argv: list[str]) -> int:
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 1
    send = "--no-telegram" not in argv

    s = load_settings()
    # fetch every proxy once
    proxy_data = {}
    for sym, spec in FUTURES_UNIVERSE.items():
        b = _proxy_bars(s, spec["proxy"], days)
        if not b.empty:
            proxy_data[sym] = b

    led = _load_ledger()
    seen = {(t["day"], t["symbol"]) for t in led["trades"]}

    # union of session dates across instruments, oldest->newest, last `days`
    all_days = sorted({d for b in proxy_data.values() for d in set(b.index.date)})[-days:]

    new_trades = []
    for day in all_days:
        # collect this day's candidate trades across instruments, cap concurrency by risk order
        day_trades = []
        for sym, spec in FUTURES_UNIVERSE.items():
            if sym not in proxy_data:
                continue
            b = proxy_data[sym]
            today = b[b.index.date == day]
            today = today.between_time("09:30", "16:00")
            if len(today) < 6 or (str(day), sym) in seen:
                continue
            day_trades += _simulate_session(sym, spec, today, led["equity"])
        # concurrency cap: the day's FIRST MAX_CONCURRENT trades by actual entry time
        # (a real account can only hold so many at once; earliest signals win the slot).
        day_trades.sort(key=lambda t: t["entry_ts"])
        for t in day_trades[:MAX_CONCURRENT]:
            led["equity"] += t["pnl"]
            led["trades"].append(t)
            new_trades.append(t)

    _save_ledger(led)

    # ---- report (its OWN dedicated message) ----
    n_all = len(led["trades"]); net_all = sum(t["pnl"] for t in led["trades"])
    w_all = sum(1 for t in led["trades"] if t["pnl"] > 0)
    wr = (w_all / n_all * 100) if n_all else 0
    head = ("🔮 <b>ORB FUTURES</b> (paper · micro index futures)\n"
            f"equity <b>${led['equity']:,.0f}</b>  ·  lifetime {n_all}t · "
            f"{wr:.0f}% win · net ${net_all:+,.0f}")
    if new_trades:
        day_net = sum(t["pnl"] for t in new_trades)
        day_w = sum(1 for t in new_trades if t["pnl"] > 0)
        lines = [f"  {t['symbol']} {t['side'].upper()} {t['contracts']}x "
                 f"@ {t['entry']} → {t['exit']} ({t['exit_kind']})  ${t['pnl']:+,.0f}"
                 for t in new_trades]
        body = (head + f"\n<b>today: {len(new_trades)} trades · {day_w}/{len(new_trades)} win · "
                f"${day_net:+,.0f}</b>\n" + "\n".join(lines))
    else:
        body = head + "\nno ORB FUTURES setups today."
    print(body.replace("<b>", "").replace("</b>", ""))

    if send and TelegramNotifier and s.telegram_token:
        TelegramNotifier(s.telegram_token, s.telegram_chat_id).send(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
