"""Small-gap fade at the open (index ETFs).

Small overnight gaps (0.1%-0.4%) on SPY/QQQ-class symbols fill the majority of the
time; large gaps are news-driven and trend instead, so those are skipped. Fade the
gap within the first `entry_window_bars` bars: gap up -> short toward yesterday's
close, gap down -> long. Target IS the fill (prev close); stop is `stop_atr` ATRs
beyond entry (ATR taken from the prior session, today's is unstable this early).

Works on stale data: the gap is measured off the official prior close and today's
open print — both known regardless of feed delay — and the target is a fixed level.
"""

from __future__ import annotations

import pandas as pd

from ..smc.signals import Signal
from ..smc.zones import atr


def generate(
    today: pd.DataFrame,
    *,
    hist: pd.DataFrame | None = None,
    min_gap: float = 0.001,
    max_gap: float = 0.004,
    entry_window_bars: int = 6,
    stop_atr: float = 2.0,
    atr_period: int = 14,
    **_,
) -> list[Signal]:
    if hist is None or hist.empty or today.empty:
        return []
    prev_close = float(hist["close"].iloc[-1])
    day_open = float(today["open"].iloc[0])
    if prev_close <= 0:
        return []
    gap = day_open / prev_close - 1.0
    if not (min_gap <= abs(gap) <= max_gap):
        return []

    prev_atr_series = atr(hist.tail(80), atr_period)
    prev_atr = float(prev_atr_series.iloc[-1]) if len(prev_atr_series) else 0.0
    if prev_atr <= 0:
        return []

    closes = today["close"].to_numpy()
    n = min(entry_window_bars, len(today))
    out: list[Signal] = []
    for i in range(1, n):
        c = float(closes[i])
        if gap > 0:
            # Gap up: short back toward yesterday's close, unless it already filled.
            if c <= prev_close:
                break
            out.append(Signal(
                index=i, side="short", entry=c, stop=c + stop_atr * prev_atr,
                target=prev_close,
                reasons=[f"gap fade: +{gap:.2%} gap, target fill {prev_close:.2f}"],
                strategy="gap_fade", entry_type="market",
            ))
        else:
            if c >= prev_close:
                break
            out.append(Signal(
                index=i, side="long", entry=c, stop=c - stop_atr * prev_atr,
                target=prev_close,
                reasons=[f"gap fade: {gap:.2%} gap, target fill {prev_close:.2f}"],
                strategy="gap_fade", entry_type="market",
            ))
        break  # one attempt per day, on the first bar inside the window
    return out
