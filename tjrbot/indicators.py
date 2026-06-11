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
