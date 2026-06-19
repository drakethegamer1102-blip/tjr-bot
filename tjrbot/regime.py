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

    Fix (2026-06-18): a 2-of-3 majority of those three direction signals now flags a
    trend, instead of requiring ALL three. Today TSLA had ADX 82.8 (violent uptrend)
    but returned neutral because one of the three didn't align at that bar, so the
    regime filter let a short through that lost ~$500. A strongly-trending stock must
    never read as neutral.
    """
    c = today["close"].to_numpy()
    vw = vwap(today).to_numpy()
    ef = ema(today["close"], ema_fast).to_numpy()
    ax = adx(today, adx_period).to_numpy()
    if i < slope_window or i >= len(c) or ax[i] < adx_min:
        return 0
    close, v = float(c[i]), float(vw[i])
    vslope = float(vw[i] - vw[i - slope_window])
    up = (close > v) + (vslope > 0) + (close > ef[i])
    dn = (close < v) + (vslope < 0) + (close < ef[i])
    if up >= 2 and up > dn:
        return 1
    if dn >= 2 and dn > up:
        return -1
    return 0


def market_bias(market_today: pd.DataFrame, *, min_pct: float = 0.4) -> int:
    """Broad-market direction for the day: +1 risk-on, -1 risk-off, 0 unclear.

    Reads the index ETF's session bars (SPY/QQQ). The day is "clearly up" when price
    is meaningfully above the open AND above session VWAP (and mirror for down). The
    2026-06-18 lesson: every stock was green (+0.3% to +2.1%) yet the bot shorted TSLA
    and MSFT into the rally on stale per-name bias — a market gate would have blocked
    both. `min_pct` is the move from the open (in %) required to call a direction.
    """
    if market_today is None or len(market_today) < 3:
        return 0
    o = float(market_today["open"].iloc[0])
    c = float(market_today["close"].iloc[-1])
    if o <= 0:
        return 0
    chg_pct = (c - o) / o * 100
    v = float(vwap(market_today).iloc[-1])
    if chg_pct >= min_pct and c > v:
        return 1
    if chg_pct <= -min_pct and c < v:
        return -1
    return 0


def market_filter(signals: list, market_bias_value: int) -> list:
    """Drop signals that fight a clear BROAD-MARKET day: no individual-name shorts on a
    clearly risk-on day, no longs on a clearly risk-off day. Index-level guard that
    complements the per-symbol `filter_signals` (a single stock can look weak intraday
    while the whole tape is ripping — that's exactly when shorts get run over)."""
    if market_bias_value == 0:
        return signals
    kept = []
    for s in signals:
        if market_bias_value == 1 and s.side == "short":
            continue
        if market_bias_value == -1 and s.side == "long":
            continue
        kept.append(s)
    return kept


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
