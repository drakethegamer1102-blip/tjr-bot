"""Daily stock strategies — paper tracker + review (DIPSNAP / PULLBACK / TUESDAY-EQ).

Runs the three validated daily stock strategies on SPY (real daily bars via yfinance),
keeps a per-strategy paper ledger, and sends its OWN Telegram message (separate from every
other product). Runs once daily after the close. Paper/simulation only.

Usage:
    python scripts/stock_daily_paper.py                # update ledger, send review
    python scripts/stock_daily_paper.py --days 250      # (re)build over last N sessions
    python scripts/stock_daily_paper.py --no-telegram
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tjrbot.config import load_settings
from tjrbot.strategies.stock_daily import REGISTRY

try:
    from tjrbot.notify.telegram import TelegramNotifier
except Exception:
    TelegramNotifier = None  # type: ignore

LEDGER = Path(__file__).resolve().parent.parent / "stock_daily_ledger.json"
START_EQUITY = 50_000.0
SHARES = 100                # fixed small size for the paper sim (100 SPY shares)
SYMBOL = "SPY"


def _load():
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except Exception:
            pass
    return {s: {"equity": START_EQUITY, "trades": []} for s in REGISTRY}


def _save(led):
    LEDGER.write_text(json.dumps(led, indent=2, default=str))


def _spy_daily():
    import yfinance as yf
    import pandas as pd
    df = yf.download(SYMBOL, period="2y", interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()


def _simulate(strat_fn, daily, n_days):
    trades = []
    idx = daily.index
    start = max(1, len(daily) - n_days - 1)
    for t in range(start, len(daily) - 1):
        plan = strat_fn(daily.iloc[: t + 1])
        if not plan:
            continue
        nxt = daily.iloc[t + 1]
        entry = float(nxt["open"]); exit_ = float(nxt["close"])
        pnl = (exit_ - entry) * SHARES     # long-only
        trades.append({
            "day": str(idx[t + 1].date()), "side": plan["side"],
            "entry": round(entry, 2), "exit": round(exit_, 2),
            "pnl": round(pnl, 2), "note": plan["note"],
        })
    return trades


def main(argv):
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 250
    send = "--no-telegram" not in argv
    s = load_settings()

    try:
        daily = _spy_daily()
    except Exception as e:  # noqa: BLE001
        print("SPY data fetch failed:", e); return 1

    led = _load()
    for name, fn in REGISTRY.items():
        book = led.setdefault(name, {"equity": START_EQUITY, "trades": []})
        seen = {t["day"] for t in book["trades"]}
        for tr in _simulate(fn, daily, days):
            if tr["day"] in seen:
                continue
            book["equity"] += tr["pnl"]
            book["trades"].append(tr)
    _save(led)

    lines = ["🟢 <b>STOCK · DAILY</b> review (paper · SPY · 100 sh)"]
    grand = 0.0
    for name in REGISTRY:
        book = led[name]; ts = book["trades"]
        net = sum(t["pnl"] for t in ts); grand += net
        n = len(ts); w = sum(1 for t in ts if t["pnl"] > 0)
        wr = (w / n * 100) if n else 0
        last = ts[-1] if ts else None
        tail = (f" · last {last['day']} ${last['pnl']:+,.0f}" if last else "")
        verdict = "🟢" if net > 0 else "🔴" if net < 0 else "⚪"
        lines.append(f"<b>{name}</b>: ${book['equity']:,.0f} · {n}t · {wr:.0f}% win · "
                     f"net ${net:+,.0f} {verdict}{tail}")
    lines.append(f"— combined paper net ${grand:+,.0f}")
    body = "\n".join(lines)
    print(body.replace("<b>", "").replace("</b>", ""))

    if send and TelegramNotifier and s.telegram_token:
        TelegramNotifier(s.telegram_token, s.telegram_chat_id).send(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
