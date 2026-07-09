"""Pre-open Telegram news brief: watchlist headlines from the last 18 hours.

Runs via CI mode "morning-brief" (external cron ~9:00 ET weekdays) or by hand:
    PYTHONPATH=. .venv/bin/python scripts/morning_brief.py [--telegram]

Shows the same headlines the engine's news gate acts on, so the user sees each
morning WHY reversion entries may be blocked on particular symbols that day.
"""

from __future__ import annotations

import sys

from tjrbot.config import load_settings
from tjrbot.news import fetch_headlines
from tjrbot.notify.telegram import TelegramNotifier

MAX_PER_SYMBOL = 3


def main(argv: list[str]) -> int:
    send = "--telegram" in argv
    s = load_settings()
    profile = s.profile
    symbols = list(profile.get("symbols", []))
    nf = s.raw.get("news_filter") or {}
    hours = float(nf.get("lookback_hours", 18))

    headlines = fetch_headlines(s.alpaca_key, s.alpaca_secret, symbols, hours=hours)
    lines = [f"Morning brief — watchlist news, last {hours:.0f}h"]
    if not headlines:
        lines.append("  No fresh headlines. News gate inactive today (so far).")
    for sym in sorted(headlines):
        lines.append(f"  {sym}:")
        for h in headlines[sym][:MAX_PER_SYMBOL]:
            lines.append(f"    • {h[:120]}")
    blocked = nf.get("block_bots") or []
    if headlines and nf.get("enabled") and blocked:
        lines.append(f"  Gate: {'/'.join(blocked)} reversion entries blocked on the symbols above.")

    report = "\n".join(lines)
    print(report)
    if send and s.telegram_token:
        TelegramNotifier(s.telegram_token, s.telegram_chat_id).send("📰 " + report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
