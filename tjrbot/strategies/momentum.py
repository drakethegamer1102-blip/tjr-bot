"""Momentum / trend breakout.

In an up-trend (fast EMA above slow EMA), go long when price breaks the highest high
of the last `lookback` bars; mirror for shorts in a down-trend. Stop = 1.5*ATR,
target = reward:risk multiple. One trade per direction per day.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import ema
from ..smc.signals import Signal
from ..smc.zones import atr


def generate(
    today: pd.DataFrame,
    *,
    ema_fast: int = 9,
    ema_slow: int = 21,
    lookback: int = 20,
    min_rr: float = 2.0,
    atr_period: int = 14,
    stop_atr: float = 1.5,
    **_,
) -> list[Signal]:
    need = max(ema_slow, lookback) + 2
    if len(today) < need:
        return []
    close = today["close"]
    c = close.to_numpy()
    high = today["high"].to_numpy()
    low = today["low"].to_numpy()
    ef = ema(close, ema_fast).to_numpy()
    es = ema(close, ema_slow).to_numpy()
    a = atr(today, atr_period).to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(lookback, len(today)):
        if a[i] <= 0:
            continue
        prior_high = float(high[i - lookback:i].max())
        prior_low = float(low[i - lookback:i].min())
        if not fired_long and c[i] > prior_high and ef[i] > es[i]:
            entry = float(c[i])
            stop = entry - stop_atr * a[i]
            out.append(Signal(i, "long", entry, stop, entry + min_rr * (entry - stop),
                              [f"break {lookback}-bar high", "EMA up"], strategy="momentum", entry_type="market"))
            fired_long = True
        elif not fired_short and c[i] < prior_low and ef[i] < es[i]:
            entry = float(c[i])
            stop = entry + stop_atr * a[i]
            out.append(Signal(i, "short", entry, stop, entry - min_rr * (stop - entry),
                              [f"break {lookback}-bar low", "EMA down"], strategy="momentum", entry_type="market"))
            fired_short = True
        if fired_long and fired_short:
            break
    return out
