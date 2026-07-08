"""Non-SMC strategies that run alongside TJR (each returns tagged Signals).

Each strategy exposes ``generate(today, **params) -> list[Signal]`` operating on a
single session's intraday bars. Signals carry `.strategy` and `.entry_type` so the
engine, backtester, and per-strategy stats can treat them uniformly.
"""

from . import (
    band_tag,
    bollinger_rev,
    gap_fade,
    macd_trend,
    momentum,
    noise_band,
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
    "noise_band": noise_band.generate,
    "gap_fade": gap_fade.generate,
    "band_tag": band_tag.generate,
}

# Strategies whose generate() also needs prior-session bars (passed as hist=).
NEEDS_HIST = {"noise_band", "gap_fade", "band_tag"}

__all__ = [
    "orb", "vwap_rev", "momentum", "rsi_pullback",
    "bollinger_rev", "macd_trend", "squeeze_breakout",
    "noise_band", "gap_fade", "band_tag", "REGISTRY", "NEEDS_HIST",
]
