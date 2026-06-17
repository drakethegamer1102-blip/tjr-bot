"""Non-SMC strategies that run alongside TJR (each returns tagged Signals).

Each strategy exposes ``generate(today, **params) -> list[Signal]`` operating on a
single session's intraday bars. Signals carry `.strategy` and `.entry_type` so the
engine, backtester, and per-strategy stats can treat them uniformly.
"""

from . import (
    bollinger_rev,
    macd_trend,
    momentum,
    orb,
    rsi_pullback,
    squeeze_breakout,
    vwap_rev,
)

REGISTRY = {
    "orb": orb.generate,
    "vwap_rev": vwap_rev.generate,
    "momentum": momentum.generate,
    "rsi_pullback": rsi_pullback.generate,
    "bollinger_rev": bollinger_rev.generate,
    "macd_trend": macd_trend.generate,
    "squeeze_breakout": squeeze_breakout.generate,
}

__all__ = [
    "orb", "vwap_rev", "momentum", "rsi_pullback",
    "bollinger_rev", "macd_trend", "squeeze_breakout", "REGISTRY",
]
