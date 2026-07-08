"""Keltner band-tag mean reversion with RSI(2) trigger and a daily-trend gate.

Price tagging a wide Keltner band (EMA20 ± kc_mult*ATR) while RSI(2) is pinned at an
extreme is a stretched move with fuel spent; it reverts toward the band midline more
often than not — but ONLY when traded with the higher-timeframe trend (Connors: buy
pullbacks above the long-term average, don't catch knives below it). The gate here:
longs only when yesterday's close is above the `sma_days`-day close average, shorts
only when below.

Entry at the tag close; target = band midline (the strategy's own edge, honored via
per-bot risk config); stop `stop_atr` ATRs beyond. Levels are computed off closed
bars, so stale data shifts fills without changing the level logic.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import ema, rsi
from ..smc.signals import Signal
from ..smc.zones import atr

ET = "America/New_York"


def _daily_sma_gate(hist: pd.DataFrame, sma_days: int) -> int:
    """+1 = longs allowed, -1 = shorts allowed, 0 = no gate data."""
    day_key = hist.index.tz_convert(ET).normalize()
    daily_close = hist.groupby(day_key)["close"].last()
    if len(daily_close) < sma_days:
        return 0
    sma = float(daily_close.tail(sma_days).mean())
    return 1 if float(daily_close.iloc[-1]) >= sma else -1


def generate(
    today: pd.DataFrame,
    *,
    hist: pd.DataFrame | None = None,
    kc_period: int = 20,
    kc_mult: float = 2.5,
    rsi_period: int = 2,
    rsi_lo: float = 5.0,
    rsi_hi: float = 95.0,
    stop_atr: float = 1.2,
    min_bars_open: int = 6,
    sma_days: int = 10,
    max_per_side: int = 2,
    atr_period: int = 14,
    **_,
) -> list[Signal]:
    if len(today) < max(kc_period, atr_period) + 2:
        return []
    gate = _daily_sma_gate(hist, sma_days) if hist is not None and not hist.empty else 0

    closes = today["close"].to_numpy()
    mid = ema(today["close"], kc_period).to_numpy()
    a = atr(today, atr_period).to_numpy()
    r = rsi(today["close"], rsi_period).to_numpy()

    out: list[Signal] = []
    n_long = n_short = 0
    start = max(kc_period, atr_period, min_bars_open)
    for i in range(start, len(today)):
        c, m, ai, ri = float(closes[i]), float(mid[i]), float(a[i]), float(r[i])
        if ai <= 0:
            continue
        upper = m + kc_mult * ai
        lower = m - kc_mult * ai
        if gate >= 0 and n_long < max_per_side and c < lower and ri <= rsi_lo and m > c:
            out.append(Signal(
                index=i, side="long", entry=c, stop=c - stop_atr * ai, target=m,
                reasons=[f"KC lower tag + RSI2={ri:.0f} (mid {m:.2f})"],
                strategy="band_tag", entry_type="limit",
            ))
            n_long += 1
        elif gate <= 0 and n_short < max_per_side and c > upper and ri >= rsi_hi and m < c:
            out.append(Signal(
                index=i, side="short", entry=c, stop=c + stop_atr * ai, target=m,
                reasons=[f"KC upper tag + RSI2={ri:.0f} (mid {m:.2f})"],
                strategy="band_tag", entry_type="limit",
            ))
            n_short += 1
    return out
