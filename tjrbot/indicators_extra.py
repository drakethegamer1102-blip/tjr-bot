"""Extra technical indicators (pure pandas): Bollinger Bands, MACD, Keltner Channels."""

from __future__ import annotations

import pandas as pd

from tjrbot.indicators import ema
from tjrbot.smc.zones import atr


def bollinger(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands — returns (middle, upper, lower).

    middle = SMA(period); upper/lower = middle +/- num_std * rolling std(period).
    """
    middle = close.rolling(period, min_periods=1).mean()
    std = close.rolling(period, min_periods=1).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return middle, upper, lower


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD — returns (macd_line, signal_line, hist).

    macd_line = ema(fast) - ema(slow); signal_line = ema(macd_line, signal);
    hist = macd_line - signal_line.
    """
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def keltner(
    bars: pd.DataFrame, period: int = 20, atr_mult: float = 1.5, atr_period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Keltner Channels — returns (middle, upper, lower).

    middle = ema(close, period); upper/lower = middle +/- atr_mult * ATR(atr_period).
    """
    middle = ema(bars["close"], period)
    a = atr(bars, atr_period)
    upper = middle + atr_mult * a
    lower = middle - atr_mult * a
    return middle, upper, lower
