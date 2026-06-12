"""Regime / trend filter — don't trade against a clear trend.

The 2026-06-11 lesson: the bot shorted into a strong up-day and every trade was
stopped out. This filter blocks counter-trend trades — no shorts in a clear uptrend,
no longs in a clear downtrend. In a range (no clear trend) both sides are allowed, so
mean-reversion can still work. Trend is judged CAUSALLY per bar (only bars <= i) and only
flags a direction when ADX shows real trend STRENGTH, so normal fades are not blocked.
Direction comes from price vs VWAP, VWAP slope, and a fast EMA. (Standard practice: trade
with the trend; fade only in ranges.) NOTE: off by default — see `regime_filter` in config.yaml.
"""

from __future__ import annotations

import pandas as pd

from .indicators import adx, ema, vwap


def trend_at(today: pd.DataFrame, i: int, *, ema_fast: int = 9, adx_period: int = 14,
             adx_min: float = 30.0, slope_window: int = 6) -> int:
    """+1 STRONG uptrend, -1 STRONG downtrend, 0 otherwise — causal, uses only bars <= i.

    Only flags a directional trend when ADX shows real trend STRENGTH (>= adx_min), so
    mean-reversion fades are still allowed in choppy/range conditions (where they have an
    edge). Direction comes from price vs VWAP, VWAP slope, and a fast EMA.
    """
    c = today["close"].to_numpy()
    vw = vwap(today).to_numpy()
    ef = ema(today["close"], ema_fast).to_numpy()
    ax = adx(today, adx_period).to_numpy()
    if i < slope_window or i >= len(c) or ax[i] < adx_min:
        return 0
    close, v = float(c[i]), float(vw[i])
    vslope = float(vw[i] - vw[i - slope_window])
    if close > v and vslope > 0 and close > ef[i]:
        return 1
    if close < v and vslope < 0 and close < ef[i]:
        return -1
    return 0


def filter_signals(signals: list, today: pd.DataFrame) -> list:
    """Drop signals that fight a clear trend at their own bar (no shorts up, no longs down)."""
    kept = []
    for s in signals:
        t = trend_at(today, s.index)
        if t == 1 and s.side == "short":
            continue
        if t == -1 and s.side == "long":
            continue
        kept.append(s)
    return kept
