"""Consistent notification labels — one taxonomy so every Telegram message is
identifiable at a glance and no two categories share an emoji.

Usage:
    from .labels import label, LIVE_TRADE
    notifier.send(label(LIVE_TRADE, "bought 100 SPY @ 740"))
      -> "💰 LIVE · bought 100 SPY @ 740"

Categories (emoji is unique per category):
  🟢 SETUP     — a live paper/live trade was placed (main bot scan)
  💰 REBOUND   — the live REBOUND strategy (real-money-capable)
  📈 FUTURES   — futures paper sims (ORB FUTURES + FUTURES DAILY)
  📋 SUMMARY   — daily / weekly performance recaps
  📰 BRIEF     — pre-open morning news brief
  🩺 HEALTH    — healthcheck / connectivity / go-live readiness
  🛡️ RISK      — safety events: EOD flatten, stale-position close, circuit breaker
  🔧 SYSTEM    — bot lifecycle / auto-tune / misc
"""

from __future__ import annotations

SETUP = ("🟢", "SETUP")
REBOUND = ("💰", "REBOUND")
FUTURES = ("📈", "FUTURES")
SUMMARY = ("📋", "SUMMARY")
BRIEF = ("📰", "BRIEF")
HEALTH = ("🩺", "HEALTH")
RISK = ("🛡️", "RISK")
SYSTEM = ("🔧", "SYSTEM")


def label(category: tuple[str, str], body: str) -> str:
    """Prefix `body` with the category's emoji + name, e.g. '📋 SUMMARY · ...'.
    If the body already starts with the emoji (message built its own header), pass through."""
    emoji, name = category
    if body.startswith(emoji):
        return body
    return f"{emoji} {name} · {body}"
