"""Entry point for the trading bot.

    python scripts/run_bot.py --dry-run --force   # scan once, print intended trades (no orders)
    python scripts/run_bot.py --once              # scan once and actually place orders (if in session)
    python scripts/run_bot.py                      # run continuously (for the always-on host)
"""

from __future__ import annotations

import argparse

from tjrbot.config import load_settings
from tjrbot.engine import cycle, run_forever
from tjrbot.journal import Journal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="decide but do not place orders")
    ap.add_argument("--once", action="store_true", help="scan a single time, then exit")
    ap.add_argument("--summary", action="store_true", help="send the end-of-day Telegram summary and exit")
    ap.add_argument("--force", action="store_true", help="ignore the session window (testing)")
    ap.add_argument("--interval", type=int, default=60, help="seconds between scans")
    args = ap.parse_args()

    s = load_settings()
    print(f"Profile: {s.profile_name} | symbols: {s.profile['symbols']} | stop_mode: {s.get('stop_mode')}")

    if args.summary:
        from tjrbot.engine import daily_summary
        from tjrbot.execution.alpaca_exec import Broker
        from tjrbot.notify.telegram import TelegramNotifier

        broker = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)
        notifier = TelegramNotifier(s.telegram_token, s.telegram_chat_id)
        print(daily_summary(s, broker, notifier, Journal()))
        return 0

    if args.once or args.dry_run:
        journal = Journal()
        broker = None
        notifier = None
        if not args.dry_run:
            from tjrbot.execution.alpaca_exec import Broker
            from tjrbot.notify.telegram import TelegramNotifier

            broker = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)
            notifier = TelegramNotifier(s.telegram_token, s.telegram_chat_id)

        actions = cycle(s, broker, notifier, journal, force=args.force)
        print(f"\n{len(actions)} action(s):")
        for a in actions:
            print("  ", a)
        if not actions:
            print("  (no fresh setups right now — this is normal; TJR setups are selective)")
        return 0

    run_forever(s, interval=args.interval, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
