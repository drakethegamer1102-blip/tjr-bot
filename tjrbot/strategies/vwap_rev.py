"""VWAP mean-reversion.

Range-bound sessions (the majority) tend to revert to VWAP. When price stretches far
from VWAP (> atr_mult * ATR) and RSI is at an extreme, fade it back toward VWAP:
short an overstretched/overbought move, long an overstretched/oversold one. Target =
VWAP; stop = 1 ATR beyond entry. (Sources: ChartsWatcher VWAP guide; Tradewink mean-reversion.)
"""

from __future__ import annotations

import pandas as pd

from ..indicators import rsi, vwap
from ..smc.zones import atr
from ..smc.signals import Signal


def generate(
    today: pd.DataFrame,
    *,
    atr_mult: float = 2.0,
    atr_period: int = 14,
    rsi_period: int = 14,
    rsi_hi: float = 70.0,
    rsi_lo: float = 30.0,
    stop_atr: float = 1.0,
    **_,
) -> list[Signal]:
    if len(today) < rsi_period + 2:
        return []
    vw = vwap(today).to_numpy()
    a = atr(today, atr_period).to_numpy()
    r = rsi(today["close"], rsi_period).to_numpy()
    closes = today["close"].to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(rsi_period, len(today)):
        c, v, ai, ri = float(closes[i]), float(vw[i]), float(a[i]), float(r[i])
        if ai <= 0:
            continue
        if not fired_short and (c - v) > atr_mult * ai and ri > rsi_hi:
            stop = c + stop_atr * ai
            out.append(Signal(i, "short", c, stop, v, [f">{atr_mult}ATR over VWAP", f"RSI {ri:.0f}"],
                              strategy="vwap_rev", entry_type="market"))
            fired_short = True
        elif not fired_long and (v - c) > atr_mult * ai and ri < rsi_lo:
            stop = c - stop_atr * ai
            out.append(Signal(i, "long", c, stop, v, [f">{atr_mult}ATR under VWAP", f"RSI {ri:.0f}"],
                              strategy="vwap_rev", entry_type="market"))
            fired_long = True
        if fired_long and fired_short:
            break
    return out
