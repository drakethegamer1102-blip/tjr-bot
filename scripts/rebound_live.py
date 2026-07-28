"""Live REBOUND runner — drives the ReboundEngine on a schedule.

REBOUND is a DAILY strategy: enter near the open (if the setup fired), exit near the close.
So this runner has two modes, triggered by your scheduler (cron-job.org / GitHub Actions):

    python scripts/rebound_live.py --open     # ~09:35 ET: enter if REBOUND fires
    python scripts/rebound_live.py --close    # ~15:55 ET: flatten the position (1-day hold)
    python scripts/rebound_live.py --status    # anytime: print state, place no orders

Safety:
  * PAPER by default (ALPACA_PAPER=true). Live requires ALPACA_PAPER=false AND
    REBOUND_LIVE_CONFIRM=I_UNDERSTAND in the environment — a deliberate two-key gate so it
    can never go live by accident.
  * Idempotent: re-running --open the same day never double-enters.
  * The --close path is the guaranteed EOD flatten; run it unconditionally near the close.
Sends a Telegram note on every action.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from tjrbot.config import load_settings
from tjrbot.execution.alpaca_exec import Broker
from tjrbot.live.rebound_engine import ReboundEngine, ReboundConfig

try:
    from tjrbot.notify.telegram import TelegramNotifier
except Exception:
    TelegramNotifier = None  # type: ignore


def _live_gate(paper: bool) -> bool:
    """Return True if it's safe to proceed. Live trading needs an explicit second key."""
    if paper:
        return True
    if os.getenv("REBOUND_LIVE_CONFIRM") == "I_UNDERSTAND":
        return True
    print("REFUSING to run LIVE without REBOUND_LIVE_CONFIRM=I_UNDERSTAND. "
          "Set ALPACA_PAPER=true to paper-trade, or set the confirm key to go live.")
    return False


def main(argv: list[str]) -> int:
    mode = next((a for a in argv if a in ("--open", "--close", "--status")), "--status")
    s = load_settings()

    from alpaca.data.historical import StockHistoricalDataClient
    data = StockHistoricalDataClient(s.alpaca_key, s.alpaca_secret)
    broker = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)

    if not _live_gate(s.alpaca_paper):
        return 2

    feed = os.getenv("REBOUND_FEED", "iex")
    eng = ReboundEngine(broker, data, ReboundConfig(feed=feed))

    tag = "PAPER" if s.alpaca_paper else "LIVE"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if mode == "--open":
        msg = eng.open_if_signal(today)
    elif mode == "--close":
        msg = eng.flatten_for_exit()
    else:
        held = broker.has_position("SPY")
        eq = broker.equity()
        msg = f"status: equity ${eq:,.0f} · holding SPY: {held}"

    line = f"🔁 REBOUND [{tag}] {mode[2:]}: {msg}"
    print(line)
    if s.telegram_token and TelegramNotifier and mode != "--status":
        TelegramNotifier(s.telegram_token, s.telegram_chat_id).send(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
