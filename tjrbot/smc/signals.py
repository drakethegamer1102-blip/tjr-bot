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
    strategy: str = "tjr"  # which strategy produced this signal
    entry_type: str = "limit"  # "limit" = fill on a retrace to entry; "market" = fill now (breakout/momentum)


def generate_signals(
    bars: pd.DataFrame,
    levels: list[float],
    pivot_strength: int = 2,
    fvg_atr_mult: float = 0.25,
    atr_period: int = 14,
    confirm_window: int = 20,
    min_rr: float = 3.0,
) -> list[Signal]:
    """Generate TJR/SMC signals.

    Fixes vs original:
    - confirm_window 10→20 bars: TJR setups take time to develop (was cutting
      off valid setups after only 50 min on 5-min bars).
    - Entry price: fvg.top for longs (retrace INTO gap from above), fvg.bottom
      for shorts — was reversed, causing entries past the gap midpoint.
    - min_rr 2.0→3.0: structural stop back to swept extreme is wide; 2R target
      was too close relative to noise. 3R better reflects TJR's next-pool target.
    - Stop buffer: add 0.05% beyond swept extreme to avoid stop-fishing at the
      exact wick low/high.
    """
    sweeps = find_sweeps(bars, levels)
    structure = detect_structure(bars, pivot_strength)
    fvgs = find_fvgs(bars, fvg_atr_mult, atr_period)
    lows = bars["low"].to_numpy()
    highs = bars["high"].to_numpy()

    signals: list[Signal] = []
    for mss in (e for e in structure if e.kind == "MSS"):
        d = mss.bias

        # Most recent same-direction sweep within the look-back window
        sweep = None
        for sw in sweeps:
            if sw.direction == d and mss.index - confirm_window <= sw.index <= mss.index:
                sweep = sw
        if sweep is None:
            continue

        # First qualifying FVG after the MSS (within look-forward window)
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
            # Long: enter at top of FVG (price retraces into gap from above)
            entry = float(fvg.top)
            stop = float(lows[sweep.index]) * 0.9995   # 0.05% buffer below swept low
            risk = entry - stop
            side = "long"
        else:
            # Short: enter at bottom of FVG (price retraces into gap from below)
            entry = float(fvg.bottom)
            stop = float(highs[sweep.index]) * 1.0005  # 0.05% buffer above swept high
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
