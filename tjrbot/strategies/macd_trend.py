"""MACD crossover with trend + zero-line filter.

Go long on a bullish MACD cross (MACD above signal) that occurs above the zero line
while price is above the trend EMA (up-trend); mirror for shorts. Stop = 1*ATR,
target = reward:risk multiple. One trade per direction per day.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import ema
from ..indicators_extra import macd
from ..smc.signals import Signal
from ..smc.zones import atr


def generate(
    today: pd.DataFrame,
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    trend_ema: int = 50,
    min_rr: float = 2.0,
    atr_period: int = 14,
    stop_atr: float = 1.0,
    **_,
) -> list[Signal]:
    warmup = slow + signal + 2
    if len(today) < warmup:
        return []
    close = today["close"]
    c = close.to_numpy()
    macd_line, signal_line, _ = macd(close, fast, slow, signal)
    ml = macd_line.to_numpy()
    sl = signal_line.to_numpy()
    te = ema(close, trend_ema).to_numpy()
    a = atr(today, atr_period).to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(warmup, len(today)):
        if i < 1 or a[i] <= 0:
            continue
        cross_up = ml[i] > sl[i] and ml[i - 1] <= sl[i - 1]
        cross_dn = ml[i] < sl[i] and ml[i - 1] >= sl[i - 1]
        if not fired_long and cross_up and ml[i] > 0 and c[i] > te[i]:
            entry = float(c[i])
            stop = entry - stop_atr * a[i]
            out.append(Signal(i, "long", entry, stop, entry + min_rr * (entry - stop),
                              ["MACD cross up", "above zero", "above trend EMA"], strategy="macd_trend", entry_type="market"))
            fired_long = True
        elif not fired_short and cross_dn and ml[i] < 0 and c[i] < te[i]:
            entry = float(c[i])
            stop = entry + stop_atr * a[i]
            out.append(Signal(i, "short", entry, stop, entry - min_rr * (stop - entry),
                              ["MACD cross down", "below zero", "below trend EMA"], strategy="macd_trend", entry_type="market"))
            fired_short = True
        if fired_long and fired_short:
            break
    return out
