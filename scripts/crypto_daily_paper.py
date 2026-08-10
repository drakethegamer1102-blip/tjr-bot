"""Daily crypto strategies — paper tracker + review (MOONSHOT / CRYPTODIP / CRYPTORSI).

Runs the three validated daily crypto strategies on BTC + ETH (real daily bars via
yfinance), keeps a per-strategy paper ledger, and sends its OWN Telegram message. Runs
once daily after the (stock) close. Crypto is 24/7, so "daily" uses the UTC-day close.
Paper/simulation only. Sizes each trade at a fixed notional so BTC and ETH are comparable.

Usage:
    python scripts/crypto_daily_paper.py                # update ledger, send review
    python scripts/crypto_daily_paper.py --days 250      # (re)build over last N days
    python scripts/crypto_daily_paper.py --no-telegram
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tjrbot.config import load_settings
from tjrbot.strategies.crypto_daily import REGISTRY

try:
    from tjrbot.notify.telegram import TelegramNotifier
except Exception:
    TelegramNotifier = None  # type: ignore

LEDGER = Path(__file__).resolve().parent.parent / "crypto_daily_ledger.json"
START_EQUITY = 50_000.0
NOTIONAL = 10_000.0          # $ per trade (paper): BTC/ETH comparable, ~5x leverage of equity is NOT used
SYMBOLS = {"BTC": "BTC-USD", "ETH": "ETH-USD"}


def _load():
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except Exception:
            pass
    return {s: {"equity": START_EQUITY, "trades": []} for s in REGISTRY}


def _save(led):
    LEDGER.write_text(json.dumps(led, indent=2, default=str))


def _daily(ticker):
    import yfinance as yf
    import pandas as pd
    df = yf.download(ticker, period="2y", interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()


def _simulate(strat_fn, daily, n_days, coin):
    trades = []
    idx = daily.index
    start = max(1, len(daily) - n_days - 1)
    for t in range(start, len(daily) - 1):
        plan = strat_fn(daily.iloc[: t + 1])
        if not plan:
            continue
        nxt = daily.iloc[t + 1]
        entry = float(nxt["open"]); exit_ = float(nxt["close"])
        units = NOTIONAL / entry               # fractional coin at a fixed $ notional
        pnl = (exit_ - entry) * units          # long-only
        trades.append({
            "day": str(idx[t + 1].date()), "coin": coin, "side": plan["side"],
            "entry": round(entry, 2), "exit": round(exit_, 2),
            "pnl": round(pnl, 2), "note": plan["note"],
        })
    return trades


def main(argv):
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 250
    send = "--no-telegram" not in argv
    s = load_settings()

    data = {}
    for coin, tk in SYMBOLS.items():
        try:
            data[coin] = _daily(tk)
        except Exception as e:  # noqa: BLE001
            print(f"{coin} fetch failed:", e)
    if not data:
        return 1

    led = _load()
    for name, fn in REGISTRY.items():
        book = led.setdefault(name, {"equity": START_EQUITY, "trades": []})
        seen = {(t["day"], t.get("coin")) for t in book["trades"]}
        for coin, daily in data.items():
            for tr in _simulate(fn, daily, days, coin):
                if (tr["day"], coin) in seen:
                    continue
                book["equity"] += tr["pnl"]
                book["trades"].append(tr)
    _save(led)

    lines = ["🪙 <b>CRYPTO · DAILY</b> review (paper · BTC+ETH · $10k/trade)"]
    grand = 0.0
    for name in REGISTRY:
        book = led[name]; ts = book["trades"]
        net = sum(t["pnl"] for t in ts); grand += net
        n = len(ts); w = sum(1 for t in ts if t["pnl"] > 0)
        wr = (w / n * 100) if n else 0
        last = ts[-1] if ts else None
        tail = (f" · last {last['day']} {last.get('coin','')} ${last['pnl']:+,.0f}" if last else "")
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
