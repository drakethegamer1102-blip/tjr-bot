"""Bollinger Band mean-reversion (dual confirmation: BB + RSI).

Range-bound sessions tend to revert to the mean. When price closes outside a
Bollinger Band AND RSI confirms the extreme, fade the move back toward the middle
band: long an oversold close below the lower band, short an overbought close above
the upper band. Target = middle band (the mean-reversion magnet); stop = 1 ATR
beyond entry.

The RSI confirmation filters out one-sided trend days where price rides a band
without reverting. Inverted trades (target on the wrong side of entry, which can
happen when the middle band sits past the close) are skipped outright.

Volume confirmation (ported from squeeze_breakout/vwap_rev, 2026-06-18): a band
break on ABOVE-average volume signals capitulation/exhaustion — the kind of move
that snaps back. Quiet drifts past the band (low volume) tend to keep going and are
skipped. This is the element that turned a PF<1 fade into a positive-expectancy one.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import rsi
from ..indicators_extra import bollinger
from ..smc.signals import Signal
from ..smc.zones import atr


def generate(
    today: pd.DataFrame,
    *,
    period: int = 20,
    num_std: float = 2.0,
    rsi_period: int = 14,
    rsi_lo: float = 30.0,
    rsi_hi: float = 70.0,
    atr_period: int = 14,
    stop_atr: float = 1.0,
    vol_period: int = 20,
    vol_mult: float = 1.3,
    **_,
) -> list[Signal]:
    warmup = max(period, vol_period) + 2
    if len(today) < warmup:
        return []
    mid, upper, lower = bollinger(today["close"], period, num_std)
    mid = mid.to_numpy()
    upper = upper.to_numpy()
    lower = lower.to_numpy()
    r = rsi(today["close"], rsi_period).to_numpy()
    a = atr(today, atr_period).to_numpy()
    closes = today["close"].to_numpy()
    volumes = today["volume"].to_numpy()
    avg_vol = today["volume"].rolling(vol_period).mean().to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(warmup, len(today)):
        ai = float(a[i])
        if ai <= 0:
            continue
        # Volume confirmation: the band break must show above-average participation.
        vi, va = float(volumes[i]), float(avg_vol[i])
        if va > 0 and vi < vol_mult * va:
            continue
        c, mi, ui, li, ri = (
            float(closes[i]), float(mid[i]), float(upper[i]), float(lower[i]), float(r[i])
        )
        # Long: close below lower band, RSI oversold; target = middle band.
        if not fired_long and c < li and ri < rsi_lo:
            if mi <= c:
                continue
            stop = c - stop_atr * ai
            out.append(Signal(i, "long", c, stop, mi,
                              [f"close<lowerBB({period},{num_std})", f"RSI {ri:.0f}",
                               f"vol {vi/va:.1f}x", "target=midBB"],
                              strategy="bollinger_rev", entry_type="market"))
            fired_long = True
        # Short: close above upper band, RSI overbought; target = middle band.
        elif not fired_short and c > ui and ri > rsi_hi:
            if mi >= c:
                continue
            stop = c + stop_atr * ai
            out.append(Signal(i, "short", c, stop, mi,
                              [f"close>upperBB({period},{num_std})", f"RSI {ri:.0f}",
                               f"vol {vi/va:.1f}x", "target=midBB"],
                              strategy="bollinger_rev", entry_type="market"))
            fired_short = True
        if fired_long and fired_short:
            break
    return out
