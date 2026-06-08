"""High-level TJR strategy: SMC signals filtered by daily bias + session window.

This is the policy layer on top of the pure detectors in `tjrbot.smc`:
  1. `daily_bias` reads higher-timeframe structure (HH/HL -> bullish, LH/LL ->
     bearish) and gives a directional lean.
  2. `find_trades` generates raw sweep -> MSS -> FVG signals, then keeps only the
     ones that (a) agree with the bias and (b) trigger inside the chosen session.
"""

from __future__ import annotations

import pandas as pd

from .smc.session import in_session
from .smc.signals import Signal, generate_signals
from .smc.structure import detect_structure


def daily_bias(htf_bars: pd.DataFrame, strength: int = 2) -> int:
    """+1 bullish / -1 bearish / 0 neutral, from the latest HTF structure break."""
    events = detect_structure(htf_bars, strength)
    return events[-1].bias if events else 0


def find_trades(
    intraday: pd.DataFrame,
    levels: list[float],
    *,
    htf_bars: pd.DataFrame | None = None,
    pivot_strength: int = 2,
    fvg_atr_mult: float = 0.25,
    atr_period: int = 14,
    confirm_window: int = 10,
    min_rr: float = 2.0,
    sessions: list[str] | None = None,
    use_bias: bool = True,
) -> list[Signal]:
    signals = generate_signals(
        intraday, levels, pivot_strength, fvg_atr_mult, atr_period, confirm_window, min_rr
    )
    bias = daily_bias(htf_bars, pivot_strength) if (use_bias and htf_bars is not None) else 0

    kept: list[Signal] = []
    for s in signals:
        if use_bias and bias != 0:
            if (s.side == "long" and bias != 1) or (s.side == "short" and bias != -1):
                continue
        if sessions:
            if not in_session(intraday.index[s.index], sessions):
                continue
        kept.append(s)
    return kept
