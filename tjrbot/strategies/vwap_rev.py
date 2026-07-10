"""VWAP mean-reversion.

Range-bound sessions (the majority) tend to revert to VWAP. When price stretches far
from VWAP (> atr_mult * ATR) and RSI is at an extreme, fade it back toward VWAP:
short an overstretched/overbought move, long an overstretched/oversold one. Target =
VWAP; stop = 1 ATR beyond entry.

Filters:
- min_bars_open: skip signals in the first N bars of the session. VWAP is unreliable
  in the first 15-30 min (opening noise, price discovery), so we wait for it to anchor.
- Volume confirmation: the signal bar must show above-average participation.

The 2026-06-12 EMA-alignment filter (short only when close < EMA20, long only when
close > EMA20) was REMOVED 2026-07-09: it contradicted the stretch requirement —
price >2.5 ATR above VWAP is virtually never below EMA20 on the same bar — so the
strategy generated ZERO trades in a 60d backtest while appearing enabled. The
anti-trend job it aimed at (don't fade MRVL on a strong up-day) is now done by the
engine-side ADX regime filter (enabled 06-12) and market-breadth filter (06-18),
which run on every signal. 60d backtest without the EMA gate, regime filter on:
31 trades, 55% win, PF 2.18, +$1,237 (vs 0 trades with it).
"""

from __future__ import annotations

import pandas as pd

from ..indicators import rsi, vwap
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
    min_bars_open: int = 6,   # skip first 30 min (6 × 5-min bars)
    vol_period: int = 20,     # rolling window for average volume
    vol_mult: float = 1.5,    # signal bar must be >= this × avg volume
    **_,
) -> list[Signal]:
    if len(today) < max(rsi_period, vol_period) + 2:
        return []
    vw = vwap(today).to_numpy()
    a = atr(today, atr_period).to_numpy()
    r = rsi(today["close"], rsi_period).to_numpy()
    closes = today["close"].to_numpy()

    volumes = today["volume"].to_numpy()
    vol_avg = pd.Series(volumes).rolling(vol_period).mean().to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    start = max(rsi_period, min_bars_open, vol_period)
    for i in range(start, len(today)):
        c, v, ai, ri = float(closes[i]), float(vw[i]), float(a[i]), float(r[i])
        if ai <= 0:
            continue
        # Volume confirmation: signal bar must show above-average participation
        vi, va = float(volumes[i]), float(vol_avg[i])
        if va > 0 and vi < vol_mult * va:
            continue
        # Short: price above VWAP by >atr_mult ATR with RSI overbought
        if not fired_short and (c - v) > atr_mult * ai and ri > rsi_hi:
            stop = c + stop_atr * ai
            out.append(Signal(i, "short", c, stop, v,
                              [f">{atr_mult}ATR over VWAP", f"RSI {ri:.0f}", f"vol {vi/va:.1f}x"],
                              strategy="vwap_rev", entry_type="market"))
            fired_short = True
        # Long: price below VWAP by >atr_mult ATR with RSI oversold
        elif not fired_long and (v - c) > atr_mult * ai and ri < rsi_lo:
            stop = c - stop_atr * ai
            out.append(Signal(i, "long", c, stop, v,
                              [f">{atr_mult}ATR under VWAP", f"RSI {ri:.0f}", f"vol {vi/va:.1f}x"],
                              strategy="vwap_rev", entry_type="market"))
            fired_long = True
        if fired_long and fired_short:
            break
    return out
