"""Verify Alpaca + Telegram connectivity. Prints only non-secret status."""

from __future__ import annotations

import sys

from tjrbot.config import load_settings
from tjrbot.notify.telegram import TelegramNotifier


def main() -> int:
    s = load_settings()
    ok = True

    # --- Alpaca ---
    try:
        from alpaca.trading.client import TradingClient

        tc = TradingClient(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)
        acct = tc.get_account()
        print(
            f"[Alpaca]   OK  status={acct.status}  equity=${float(acct.equity):,.2f}  "
            f"buying_power=${float(acct.buying_power):,.2f}  paper={s.alpaca_paper}"
        )
    except Exception as e:  # noqa: BLE001 - report any connection problem plainly
        ok = False
        print(f"[Alpaca]   FAILED: {e}")

    # --- Telegram ---
    tg = TelegramNotifier(s.telegram_token, s.telegram_chat_id)
    sent = tg.send(
        "✅ <b>TJR bot connected.</b>\nThis is a test alert — your phone "
        "notifications are working."
    )
    print(f"[Telegram] {'OK (test message sent to your phone)' if sent else 'FAILED (check token/chat id)'}")
    ok = ok and sent

    print("\nAll good — ready to trade (paper)." if ok else "\nSome checks failed (see above).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
