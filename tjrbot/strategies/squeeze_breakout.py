"""Bollinger/Keltner squeeze volatility breakout (TTM-squeeze style).

Volatility contracts before it expands. A "squeeze" is on when the Bollinger Bands sit
entirely INSIDE the Keltner Channel (bb_upper < kc_upper and bb_lower > kc_lower) — a
period of low volatility that tends to precede a directional move. We wait for the
squeeze to release: fire a breakout when a recent squeeze (any of the last
`squeeze_lookback` bars) has just ended and price closes outside the Bollinger Bands on
expanding volume. Long on a close above the upper band, short on a close below the lower
band. entry = close (market), stop = stop_atr*ATR away, target = reward:risk multiple.
One trade per direction per day.
"""

from __future__ import annotations

import pandas as pd

from ..indicators_extra import bollinger, keltner
from ..smc.signals import Signal
from ..smc.zones import atr


def generate(
    today: pd.DataFrame,
    *,
    bb_period: int = 20,
    bb_std: float = 2.0,
    kc_period: int = 20,
    kc_atr_mult: float = 1.5,
    squeeze_lookback: int = 6,
    vol_period: int = 20,
    vol_mult: float = 1.2,
    min_rr: float = 2.0,
    atr_period: int = 14,
    stop_atr: float = 1.0,
    **_,
) -> list[Signal]:
    warmup = max(bb_period, kc_period, vol_period) + 2
    if len(today) < warmup:
        return []
    close = today["close"]
    c = close.to_numpy()
    vol = today["volume"].to_numpy()
    # indicators_extra returns (middle, upper, lower) — unpack in THAT order.
    _bb_mid, bb_upper, bb_lower = bollinger(close, bb_period, bb_std)
    _kc_mid, kc_upper, kc_lower = keltner(today, kc_period, kc_atr_mult)
    bbu = bb_upper.to_numpy()
    bbl = bb_lower.to_numpy()
    kcu = kc_upper.to_numpy()
    kcl = kc_lower.to_numpy()
    squeeze_on = (bbu < kcu) & (bbl > kcl)
    avg_vol = today["volume"].rolling(vol_period).mean().to_numpy()
    a = atr(today, atr_period).to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(warmup, len(today)):
        if a[i] <= 0:
            continue
        if not squeeze_on[i - 1]:
            continue
        recent_squeeze = bool(squeeze_on[i - squeeze_lookback:i].any())
        if not recent_squeeze:
            continue
        vol_ok = vol[i] > vol_mult * avg_vol[i]
        if not vol_ok:
            continue
        if not fired_long and c[i] > bbu[i]:
            entry = float(c[i])
            stop = entry - stop_atr * a[i]
            out.append(Signal(i, "long", entry, stop, entry + min_rr * (entry - stop),
                              ["squeeze release", "close > BB upper", "volume surge"],
                              strategy="squeeze_breakout", entry_type="market"))
            fired_long = True
        elif not fired_short and c[i] < bbl[i]:
            entry = float(c[i])
            stop = entry + stop_atr * a[i]
            out.append(Signal(i, "short", entry, stop, entry - min_rr * (stop - entry),
                              ["squeeze release", "close < BB lower", "volume surge"],
                              strategy="squeeze_breakout", entry_type="market"))
            fired_short = True
        if fired_long and fired_short:
            break
    return out
