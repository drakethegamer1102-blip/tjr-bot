"""Common technical indicators (pure pandas) used by the non-SMC strategies."""

from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder-style RSI."""
    delta = close.diff()
    up = delta.clip(lower=0)
    down = (-delta).clip(lower=0)
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def vwap(bars: pd.DataFrame) -> pd.Series:
    """Cumulative VWAP over the given bars (pass one session's bars for intraday VWAP)."""
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3
    pv = (typical * bars["volume"]).cumsum()
    vol = bars["volume"].cumsum().replace(0, 1e-9)
    return pv / vol


def adx(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (Wilder) — measures trend STRENGTH (not direction).

    High ADX (>~30) = strongly trending; low (<~20) = choppy/range-bound.
    """
    high, low, close = bars["high"], bars["low"], bars["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = ((up > down) & (up > 0)) * up
    minus_dm = ((down > up) & (down > 0)) * down
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean().replace(0, 1e-9)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-9)
    return dx.ewm(alpha=1 / period, adjust=False).mean()
