"""Imbalances (FVG), order blocks, liquidity sweeps, and ATR."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FVG:
    index: int  # index of the 3rd candle that completes the gap
    top: float
    bottom: float
    direction: int  # +1 bullish, -1 bearish


@dataclass(frozen=True)
class OrderBlock:
    index: int
    top: float
    bottom: float
    direction: int  # +1 bullish, -1 bearish


@dataclass(frozen=True)
class Sweep:
    index: int
    level: float
    direction: int  # +1 swept a low (bullish), -1 swept a high (bearish)


def atr(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (simple moving average of true range)."""
    high = bars["high"]
    low = bars["low"]
    prev_close = bars["close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def find_fvgs(
    bars: pd.DataFrame, atr_mult: float = 0.25, atr_period: int = 14
) -> list[FVG]:
    """Three-candle imbalances, filtered so tiny gaps (< atr_mult*ATR) are dropped.

    Bullish FVG: ``low[i] > high[i-2]`` (gap left below price).
    Bearish FVG: ``high[i] < low[i-2]`` (gap left above price).
    """
    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    a = atr(bars, atr_period).to_numpy()
    out: list[FVG] = []
    for i in range(2, len(bars)):
        thresh = atr_mult * a[i]
        if lows[i] > highs[i - 2] and (lows[i] - highs[i - 2]) >= thresh:
            out.append(FVG(i, float(lows[i]), float(highs[i - 2]), +1))
        elif highs[i] < lows[i - 2] and (lows[i - 2] - highs[i]) >= thresh:
            out.append(FVG(i, float(lows[i - 2]), float(highs[i]), -1))
    return out


def find_sweeps(bars: pd.DataFrame, levels: list[float]) -> list[Sweep]:
    """Detect liquidity sweeps of the given price levels.

    Bullish sweep: a bar wicks BELOW a level (grabbing sell stops) then closes
    back ABOVE it. Bearish sweep: wicks above and closes back below.
    """
    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    out: list[Sweep] = []
    for i in range(len(bars)):
        for lvl in levels:
            if lows[i] < lvl and closes[i] > lvl:
                out.append(Sweep(i, float(lvl), +1))
            elif highs[i] > lvl and closes[i] < lvl:
                out.append(Sweep(i, float(lvl), -1))
    return out


def find_order_block(
    bars: pd.DataFrame, impulse_index: int, direction: int, lookback: int = 5
) -> OrderBlock | None:
    """The last opposite-colour candle before an impulsive move.

    Bullish OB = last down candle before an up impulse; bearish OB = last up
    candle before a down impulse. Returns the candle's full range as the zone.
    """
    o = bars["open"].to_numpy()
    c = bars["close"].to_numpy()
    h = bars["high"].to_numpy()
    low = bars["low"].to_numpy()
    start = max(0, impulse_index - lookback)
    for j in range(impulse_index - 1, start - 1, -1):
        if direction == +1 and c[j] < o[j]:
            return OrderBlock(j, float(h[j]), float(low[j]), +1)
        if direction == -1 and c[j] > o[j]:
            return OrderBlock(j, float(h[j]), float(low[j]), -1)
    return None
