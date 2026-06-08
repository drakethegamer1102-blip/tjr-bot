"""Market-structure primitives for the TJR / Smart-Money-Concepts strategy.

These are *mechanical approximations* of concepts TJR reads discretionarily by
eye. Definitions used here:

- **Swing high**: a bar whose high is the strict maximum of the `strength` bars
  on each side. **Swing low**: symmetric, using lows. A swing is only "known"
  `strength` bars after it prints (you cannot confirm it until the right-hand
  bars exist) — the detector respects that lag so signals are not look-ahead.
- **BOS (Break of Structure)**: price closes beyond the most recent swing in the
  SAME direction as the current bias -> trend *continuation*.
- **MSS (Market Structure Shift / CHoCH)**: price closes beyond the most recent
  swing that *flips* the bias -> potential *reversal*. This is the confirmation
  TJR waits for right after a liquidity sweep.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    kind: str  # "high" | "low"


@dataclass(frozen=True)
class StructureEvent:
    index: int
    price: float
    kind: str  # "BOS" | "MSS"
    bias: int  # +1 bullish break, -1 bearish break


def find_swings(bars: pd.DataFrame, strength: int = 2) -> list[Swing]:
    """Return confirmed swing highs and lows using a symmetric fractal."""
    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    n = len(bars)
    swings: list[Swing] = []
    for i in range(strength, n - strength):
        wh = highs[i - strength : i + strength + 1]
        if highs[i] == wh.max() and (wh == highs[i]).sum() == 1:
            swings.append(Swing(i, float(highs[i]), "high"))
        wl = lows[i - strength : i + strength + 1]
        if lows[i] == wl.min() and (wl == lows[i]).sum() == 1:
            swings.append(Swing(i, float(lows[i]), "low"))
    return swings


def detect_structure(bars: pd.DataFrame, strength: int = 2) -> list[StructureEvent]:
    """Walk the bars chronologically and emit BOS / MSS events.

    A swing found at index ``s`` is only treated as known from bar ``s+strength``
    onward, which keeps the detector causal (no peeking into the future).
    """
    swings = sorted(find_swings(bars, strength), key=lambda s: s.index)
    closes = bars["close"].to_numpy()
    n = len(bars)

    events: list[StructureEvent] = []
    bias = 0
    last_high: Swing | None = None
    last_low: Swing | None = None
    si = 0

    for i in range(n):
        # Register swings that have become confirmed by bar i.
        while si < len(swings) and swings[si].index + strength <= i:
            s = swings[si]
            if s.kind == "high":
                last_high = s
            else:
                last_low = s
            si += 1

        c = closes[i]
        if last_high is not None and c > last_high.price:
            kind = "BOS" if bias == 1 else "MSS"
            events.append(StructureEvent(i, float(c), kind, +1))
            bias = 1
            last_high = None  # consume; wait for a fresh swing high before re-firing
        elif last_low is not None and c < last_low.price:
            kind = "BOS" if bias == -1 else "MSS"
            events.append(StructureEvent(i, float(c), kind, -1))
            bias = -1
            last_low = None
    return events
