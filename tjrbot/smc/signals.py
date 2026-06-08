"""Combine SMC primitives into TJR-style entry signals.

The TJR sequence (long example):
  1. A bullish **liquidity sweep**: price grabs sell-stops below a key low, then
     closes back above it.
  2. A bullish **MSS** within ``confirm_window`` bars: structure shifts up,
     confirming the reversal.
  3. An entry on the retrace into a bullish **FVG** (the imbalance the impulse
     left behind).

Stop goes just beyond the swept extreme; target is a reward:risk multiple of
that distance (a stand-in for the next opposing liquidity pool, refined later).
Shorts are the mirror image.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .structure import detect_structure
from .zones import find_fvgs, find_sweeps


@dataclass
class Signal:
    index: int  # bar index of the entry (the completing FVG candle)
    side: str  # "long" | "short"
    entry: float
    stop: float
    target: float
    reasons: list[str] = field(default_factory=list)


def generate_signals(
    bars: pd.DataFrame,
    levels: list[float],
    pivot_strength: int = 2,
    fvg_atr_mult: float = 0.25,
    atr_period: int = 14,
    confirm_window: int = 10,
    min_rr: float = 2.0,
) -> list[Signal]:
    sweeps = find_sweeps(bars, levels)
    structure = detect_structure(bars, pivot_strength)
    fvgs = find_fvgs(bars, fvg_atr_mult, atr_period)
    lows = bars["low"].to_numpy()
    highs = bars["high"].to_numpy()

    signals: list[Signal] = []
    # Anchor on each MSS (the reversal confirmation), then look back for the
    # sweep that set it up and forward for the FVG to enter on.
    for mss in (e for e in structure if e.kind == "MSS"):
        d = mss.bias

        sweep = None  # most recent same-direction sweep within the window
        for sw in sweeps:
            if sw.direction == d and mss.index - confirm_window <= sw.index <= mss.index:
                sweep = sw
        if sweep is None:
            continue

        fvg = next(
            (
                f
                for f in fvgs
                if f.direction == d and mss.index <= f.index <= mss.index + confirm_window
            ),
            None,
        )
        if fvg is None:
            continue

        if d == +1:
            entry = float(fvg.bottom)
            stop = float(lows[sweep.index])
            risk = entry - stop
            side = "long"
        else:
            entry = float(fvg.top)
            stop = float(highs[sweep.index])
            risk = stop - entry
            side = "short"
        if risk <= 0:
            continue

        target = entry + min_rr * risk if d == +1 else entry - min_rr * risk
        signals.append(
            Signal(
                index=fvg.index,
                side=side,
                entry=entry,
                stop=stop,
                target=float(target),
                reasons=[f"sweep@{sweep.index}", f"MSS@{mss.index}", f"FVG@{fvg.index}"],
            )
        )
    return signals
