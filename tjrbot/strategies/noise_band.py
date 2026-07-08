"""Noise-band intraday momentum (Zarattini/Aziz/Barbon "Beat the Market" style).

Around the session open, price movement smaller than its typical time-of-day range is
noise; a push BEYOND that envelope tends to continue (intraday momentum). Bands are
built from the average absolute move-from-open at each bar position over the previous
`lookback_days` sessions: upper = open*(1 + k*sigma_t), lower = open*(1 - k*sigma_t).

Entry: close breaks a band (after the first `min_bars_open` bars) with VWAP alignment
(long only above VWAP, short only below) — trend confirmation, not a fade. Stop is
`stop_atr` ATRs back; target rides at `rr` R. The EOD flatten realizes whatever the
trend gave beyond the last closed bar. Bands are precomputed levels, so a ~15-min
stale feed shifts the entry, not the logic — the band was crossed either way.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import vwap
from ..smc.signals import Signal
from ..smc.zones import atr

ET = "America/New_York"


def _sigma_by_bar(hist: pd.DataFrame, lookback_days: int) -> list[float]:
    """Average |move from day open| per bar position over the last N sessions."""
    day_key = hist.index.tz_convert(ET).normalize()
    per_day: list[pd.Series] = []
    for _, day in list(hist.groupby(day_key))[-lookback_days:]:
        opens = float(day["open"].iloc[0])
        if opens <= 0 or len(day) < 10:
            continue
        per_day.append((day["close"] / opens - 1.0).abs().reset_index(drop=True))
    if len(per_day) < 5:
        return []
    return pd.concat(per_day, axis=1).mean(axis=1).tolist()


def generate(
    today: pd.DataFrame,
    *,
    hist: pd.DataFrame | None = None,
    lookback_days: int = 14,
    band_k: float = 1.0,
    min_bars_open: int = 6,
    stop_atr: float = 1.5,
    rr: float = 2.0,
    atr_period: int = 14,
    **_,
) -> list[Signal]:
    if hist is None or hist.empty or len(today) < min_bars_open + 2:
        return []
    sigma = _sigma_by_bar(hist, lookback_days)
    if not sigma:
        return []

    day_open = float(today["open"].iloc[0])
    closes = today["close"].to_numpy()
    vw = vwap(today).to_numpy()
    a = atr(today, atr_period).to_numpy()

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(min_bars_open, len(today)):
        s_t = sigma[min(i, len(sigma) - 1)]
        upper = day_open * (1 + band_k * s_t)
        lower = day_open * (1 - band_k * s_t)
        c, ai = float(closes[i]), float(a[i])
        if ai <= 0 or s_t <= 0:
            continue
        if not fired_long and c > upper and c > vw[i]:
            risk = stop_atr * ai
            out.append(Signal(
                index=i, side="long", entry=c, stop=c - risk, target=c + rr * risk,
                reasons=[f"noise-band break up (band {upper:.2f}, sigma {s_t:.3%})"],
                strategy="noise_band", entry_type="market",
            ))
            fired_long = True
        elif not fired_short and c < lower and c < vw[i]:
            risk = stop_atr * ai
            out.append(Signal(
                index=i, side="short", entry=c, stop=c + risk, target=c - rr * risk,
                reasons=[f"noise-band break down (band {lower:.2f}, sigma {s_t:.3%})"],
                strategy="noise_band", entry_type="market",
            ))
            fired_short = True
    return out
