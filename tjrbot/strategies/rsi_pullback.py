"""RSI pullback in the direction of the trend (Connors-style RSI(2)).

In an up-trend (price above the trend EMA), buy a short-term oversold dip (RSI(2) low);
in a down-trend, short an overbought bounce. Stop = 1*ATR, target = reward:risk multiple.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import ema, rsi
from ..smc.signals import Signal
from ..smc.zones import atr


def generate(
    today: pd.DataFrame,
    *,
    rsi_period: int = 2,
    lo: float = 10.0,
    hi: float = 90.0,
    trend_ema: int = 50,
    min_rr: float = 1.5,
    atr_period: int = 14,
    stop_atr: float = 1.0,
    **_,
) -> list[Signal]:
    if len(today) < trend_ema + 2:
        return []
    close = today["close"]
    c = close.to_numpy()
    te = ema(close, trend_ema).to_numpy()
    r = rsi(close, rsi_period).to_numpy()
    a = atr(today, atr_period).to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(trend_ema, len(today)):
        if a[i] <= 0:
            continue
        if not fired_long and c[i] > te[i] and r[i] < lo:
            entry = float(c[i])
            stop = entry - stop_atr * a[i]
            out.append(Signal(i, "long", entry, stop, entry + min_rr * (entry - stop),
                              [f"RSI{rsi_period}<{lo:.0f}", "above trend EMA"], strategy="rsi_pullback", entry_type="market"))
            fired_long = True
        elif not fired_short and c[i] < te[i] and r[i] > hi:
            entry = float(c[i])
            stop = entry + stop_atr * a[i]
            out.append(Signal(i, "short", entry, stop, entry - min_rr * (stop - entry),
                              [f"RSI{rsi_period}>{hi:.0f}", "below trend EMA"], strategy="rsi_pullback", entry_type="market"))
            fired_short = True
        if fired_long and fired_short:
            break
    return out
