"""Daily futures strategies — paper tracker + daily review (DAYBREAK / REBOUND / TIDERIDER).

Runs the three validated daily ES-futures strategies on REAL ES=F data (yfinance), keeps a
per-strategy paper ledger, and sends ONE combined Telegram review with each strategy on its
own line. Designed to run once daily after the close. Paper/simulation only — no broker.

Because these are DAILY-bar strategies, "today's" decision is evaluated against the most
recent completed sessions; the realized P&L of the last closed trade (entered at yesterday's
open-equivalent, exited at the close) is what gets banked each run.

Usage:
    python scripts/futures_daily_paper.py                 # update ledger, send review
    python scripts/futures_daily_paper.py --days 60        # (re)build over last N sessions
    python scripts/futures_daily_paper.py --no-telegram
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tjrbot.config import load_settings
from tjrbot.strategies.futures_daily import REGISTRY as _REG1
from tjrbot.strategies.futures_daily_v2 import REGISTRY as _REG2

# all six validated daily futures strategies: DAYBREAK/REBOUND/GAPFILL + TUESDAY/CAPITULATION/UPRIDE
REGISTRY = {**_REG1, **_REG2}

try:
    from tjrbot.notify.telegram import TelegramNotifier
except Exception:
    TelegramNotifier = None  # type: ignore

LEDGER = Path(__file__).resolve().parent.parent / "futures_daily_ledger.json"
START_EQUITY = 50_000.0
MES_POINT_VALUE = 5.0       # micro contract $/point (paper sim uses MES)
CONTRACTS = 2               # fixed small size for the paper sim (2 MES ~= modest risk)


def _load():
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except Exception:
            pass
    return {s: {"equity": START_EQUITY, "trades": []} for s in REGISTRY}


def _save(led):
    LEDGER.write_text(json.dumps(led, indent=2, default=str))


def _es_daily():
    """Real ES=F daily bars, normalized to lowercase OHLC with a DatetimeIndex."""
    import yfinance as yf
    import pandas as pd
    df = yf.download("ES=F", period="2y", interval="1d", progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
    return df


def _simulate(strat_fn, daily, n_days):
    """Replay the strategy over the last n_days sessions; return list of closed trades.
    Each strategy decides at day t (using data through t) for entry at t+1 open, exit at
    t+1 close. We evaluate every day where a full t+1 exists."""
    trades = []
    idx = daily.index
    start = max(1, len(daily) - n_days - 1)
    for t in range(start, len(daily) - 1):
        window = daily.iloc[: t + 1]                 # data known at close of day t
        plan = strat_fn(window)
        if not plan:
            continue
        nxt = daily.iloc[t + 1]                       # the session we trade
        entry = float(nxt["open"]); exit_ = float(nxt["close"])
        # GAPFILL only trades if the next open actually gapped down enough vs prior close.
        gap_req = plan.get("requires_gap_down_pct")
        if gap_req is not None:
            prev_close = plan["prev_close"]
            if entry > prev_close * (1 - gap_req):    # not a big enough gap-down -> skip
                continue
        pts = (exit_ - entry) if plan["side"] == "long" else (entry - exit_)
        trades.append({
            "day": str(idx[t + 1].date()), "side": plan["side"],
            "entry": round(entry, 2), "exit": round(exit_, 2),
            "points": round(pts, 2), "pnl": round(pts * MES_POINT_VALUE * CONTRACTS, 2),
            "note": plan["note"],
        })
    return trades


def main(argv):
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 60
    send = "--no-telegram" not in argv
    s = load_settings()

    try:
        daily = _es_daily()
    except Exception as e:  # noqa: BLE001
        print("ES data fetch failed:", e); return 1

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

    # ---- combined review, one line per strategy ----
    lines = ["📈 <b>FUTURES · DAILY</b> review (paper · real ES=F · MES ×2)"]
    grand = 0.0
    for name in REGISTRY:
        book = led[name]; ts = book["trades"]
        net = sum(t["pnl"] for t in ts); grand += net
        n = len(ts); w = sum(1 for t in ts if t["pnl"] > 0)
        wr = (w / n * 100) if n else 0
        last = ts[-1] if ts else None
        tail = (f" · last {last['day']} {last['side']} ${last['pnl']:+,.0f}" if last else "")
        lines.append(f"<b>{name}</b>: ${book['equity']:,.0f} · {n}t · {wr:.0f}% win · "
                     f"net ${net:+,.0f}{tail}")
    lines.append(f"— combined paper net ${grand:+,.0f}")
    body = "\n".join(lines)
    print(body.replace("<b>", "").replace("</b>", ""))

    if send and TelegramNotifier and s.telegram_token:
        TelegramNotifier(s.telegram_token, s.telegram_chat_id).send(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
