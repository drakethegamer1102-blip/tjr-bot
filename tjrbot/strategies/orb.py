"""Opening Range Breakout (ORB).

Long when a bar closes above the opening-range high *and* above VWAP; short when it
closes below the opening-range low and below VWAP. Stop = opposite side of the range,
target = a reward:risk multiple. One trade per direction per day, taken on the first
qualifying breakout. (Sources: Forextester ORB guide; HighStrike; QuantVPS.)
"""

from __future__ import annotations

import pandas as pd

from ..indicators import vwap
from ..smc.zones import atr
from ..smc.signals import Signal


def generate(
    today: pd.DataFrame,
    *,
    or_minutes: int = 15,
    min_rr: float = 2.0,
    atr_period: int = 14,
    max_or_atr: float = 4.0,
    **_,
) -> list[Signal]:
    if len(today) < 4:
        return []
    start = today.index[0]
    or_end = start + pd.Timedelta(minutes=or_minutes)
    or_bars = today[today.index < or_end]
    n_or = len(or_bars)
    if n_or < 1 or n_or >= len(today):
        return []

    orh = float(or_bars["high"].max())
    orl = float(or_bars["low"].min())
    vw = vwap(today).to_numpy()
    a = atr(today, atr_period).to_numpy()
    closes = today["close"].to_numpy()

    # Skip if the opening range is abnormally wide (stops/targets would be huge).
    if a[n_or - 1] > 0 and (orh - orl) > max_or_atr * a[n_or - 1]:
        return []

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(n_or, len(today)):
        c = float(closes[i])
        v = float(vw[i])
        if not fired_long and c > orh and c > v:
            risk = c - orl
            if risk > 0:
                out.append(Signal(i, "long", c, orl, c + min_rr * risk,
                                  [f"break>{orh:.2f}", "above VWAP"], strategy="orb", entry_type="market"))
                fired_long = True
        elif not fired_short and c < orl and c < v:
            risk = orh - c
            if risk > 0:
                out.append(Signal(i, "short", c, orh, c - min_rr * risk,
                                  [f"break<{orl:.2f}", "below VWAP"], strategy="orb", entry_type="market"))
                fired_short = True
        if fired_long and fired_short:
            break
    return out
