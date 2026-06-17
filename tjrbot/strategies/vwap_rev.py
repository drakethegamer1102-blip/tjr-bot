"""VWAP mean-reversion.

Range-bound sessions (the majority) tend to revert to VWAP. When price stretches far
from VWAP (> atr_mult * ATR) and RSI is at an extreme, fade it back toward VWAP:
short an overstretched/overbought move, long an overstretched/oversold one. Target =
VWAP; stop = 1 ATR beyond entry.

Filters added after chart review (2026-06-12):
- EMA trend filter: only long when close > EMA(ema_period), only short when close <
  EMA(ema_period). Prevents fading a move that IS the trend (e.g. shorting MRVL on a
  strong up-day, buying AAPL on a sustained down-day).
- min_bars_open: skip signals in the first N bars of the session. VWAP is unreliable
  in the first 15-30 min (opening noise, price discovery), so we wait for it to anchor.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import ema, rsi, vwap
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
    ema_period: int = 20,
    min_bars_open: int = 6,   # skip first 30 min (6 × 5-min bars)
    vol_period: int = 20,     # rolling window for average volume
    vol_mult: float = 1.5,    # signal bar must be >= this × avg volume
    **_,
) -> list[Signal]:
    if len(today) < max(rsi_period, ema_period) + 2:
        return []
    vw = vwap(today).to_numpy()
    a = atr(today, atr_period).to_numpy()
    r = rsi(today["close"], rsi_period).to_numpy()
    em = ema(today["close"], ema_period).to_numpy()
    closes = today["close"].to_numpy()

    volumes = today["volume"].to_numpy()
    vol_avg = pd.Series(volumes).rolling(vol_period).mean().to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    start = max(rsi_period, ema_period, min_bars_open, vol_period)
    for i in range(start, len(today)):
        c, v, ai, ri, ei = (
            float(closes[i]), float(vw[i]), float(a[i]), float(r[i]), float(em[i])
        )
        if ai <= 0:
            continue
        # Volume confirmation: signal bar must show above-average participation
        vi, va = float(volumes[i]), float(vol_avg[i])
        if va > 0 and vi < vol_mult * va:
            continue
        # Short: price above VWAP by >atr_mult ATR, RSI overbought, AND below EMA (trend is down)
        if not fired_short and (c - v) > atr_mult * ai and ri > rsi_hi and c < ei:
            stop = c + stop_atr * ai
            out.append(Signal(i, "short", c, stop, v,
                              [f">{atr_mult}ATR over VWAP", f"RSI {ri:.0f}", f"c<EMA{ema_period}", f"vol {vi/va:.1f}x"],
                              strategy="vwap_rev", entry_type="market"))
            fired_short = True
        # Long: price below VWAP by >atr_mult ATR, RSI oversold, AND above EMA (trend is up)
        elif not fired_long and (v - c) > atr_mult * ai and ri < rsi_lo and c > ei:
            stop = c - stop_atr * ai
            out.append(Signal(i, "long", c, stop, v,
                              [f">{atr_mult}ATR under VWAP", f"RSI {ri:.0f}", f"c>EMA{ema_period}", f"vol {vi/va:.1f}x"],
                              strategy="vwap_rev", entry_type="market"))
            fired_long = True
        if fired_long and fired_short:
            break
    return out
