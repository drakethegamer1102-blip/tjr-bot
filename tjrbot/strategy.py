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
from .smc.structure import detect_structure, find_swings


def daily_bias(htf_bars: pd.DataFrame, strength: int = 2) -> int:
    """+1 bullish / -1 bearish / 0 neutral HTF lean.

    Robust read (2026-06-13 rewrite): a single most-recent structure break is far
    too noisy — one bearish CHoCH on a thin 1h window flipped the whole day bearish,
    which produced June 11's all-short loss day. Instead we combine two signals and
    require them to AGREE, else return neutral (0 = take both sides):

      1. Swing sequence: the last few confirmed swing highs/lows. Higher-highs AND
         higher-lows -> bullish; lower-highs AND lower-lows -> bearish.
      2. Structure events: the *net* of recent BOS/MSS biases (majority vote), not
         just the final one.

    Neutral is a feature: when the HTF is choppy the bot is allowed to trade both
    directions (mean-reversion still works in a range), it just won't be FORCED
    one-way by noise.
    """
    # Need enough bars to form at least two confirmed swings each side; below this a
    # bias read is just noise (the June-11 failure mode) -> stay neutral.
    if htf_bars is None or len(htf_bars) < strength * 4 + 6:
        return 0

    # Primary read: NET direction of the last few structure breaks (BOS/MSS), not
    # just the single most-recent one. A lone bearish CHoCH no longer flips the day.
    events = detect_structure(htf_bars, strength)
    if not events:
        return 0
    recent = events[-4:]
    net = sum(e.bias for e in recent)
    event_bias = 1 if net > 0 else (-1 if net < 0 else 0)
    if event_bias == 0:
        return 0  # breaks are balanced -> genuinely two-sided -> neutral

    # Veto: if the swing sequence CLEARLY contradicts the event read, stand down to
    # neutral rather than commit one-way. (Swings agreeing or merely being unclear is
    # fine — only an opposite, unambiguous swing read vetoes.)
    swing_bias = _swing_sequence_bias(htf_bars, strength)
    if swing_bias != 0 and swing_bias != event_bias:
        return 0
    return event_bias


def _swing_sequence_bias(htf_bars: pd.DataFrame, strength: int) -> int:
    """+1 if last two swing highs AND lows are both rising (HH+HL), -1 if both
    falling (LH+LL), else 0."""
    swings = find_swings(htf_bars, strength)
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return 0
    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    lh = highs[-1].price < highs[-2].price
    ll = lows[-1].price < lows[-2].price
    if hh and hl:
        return 1
    if lh and ll:
        return -1
    return 0


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
