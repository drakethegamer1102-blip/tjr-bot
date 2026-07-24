"""Confluence VWAP reversion — a merge of the fundamentals that actually win here.

This strategy is deliberately built from the shared DNA of the three strategies that
survived the 2026-07-21 audit (vwap_rev, band_tag, orb) plus the web-research evidence
on VWAP mean reversion. It fires only when SEVERAL independent edges line up at once —
hence "confluence" — which is what pushes a fade from a coin-flip to a real edge.

Winning fundamentals it inherits:

1. VWAP anchor (from vwap_rev / orb). Instead of vwap_rev's "N ATRs from VWAP" we use
   the volume-weighted standard-deviation band (price this far from VWAP happens ~5% of
   the time). Research: a 2-sigma VWAP stretch reverts ~63% of the time intraday
   (QuantConnect / quantifiedstrategies). Target is VWAP itself; stop sits beyond the
   3-sigma band (mirrors the published "stop past 3 SD, target VWAP" rule).

2. RSI(2) extreme trigger (from band_tag). A stretched price with RSI pinned at an
   extreme is a move with its fuel spent — the timing trigger on top of the location.

3. Daily-trend gate (from band_tag, Connors-style). Only fade WITH the higher-timeframe
   trend: longs only when yesterday's close is above the sma_days average, shorts only
   below. Fading against the daily trend is how reversion gets run over — this is the
   single most important filter per the research ("fails badly on strong trend days").

4. Volume confirmation (from vwap_rev / orb). The tag bar must show above-average
   participation — a real institutional-flow stretch, not a thin drift.

5. limit (retrace) entry (from band_tag). Entry is a resting limit at the tag price, not
   a market order. This is the latency-safe fill mode: it is IMMUNE to the 15-min IEX
   delay that killed the market-entry breakout strategies (momentum/macd_trend), because
   the level is computed off a closed bar and the fill only happens if price actually
   returns to it. Fading INTO a data delay helps a reversion trade instead of hurting it.

6. Session-timing discipline (from vwap_rev min_bars_open + research). Skip the first
   30 min (VWAP not yet anchored) and the mid-day lull (11:30-14:00 ET) where VWAP
   reversion is least reliable; concentrate on the first 90 min and the afternoon.

Engine-side, this also passes through the ADX regime filter + market-breadth filter like
every other RIPTIDE signal, and honors its own VWAP target via the per-bot risk config.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import rsi, vwap
from ..smc.signals import Signal
from ..smc.zones import atr

ET = "America/New_York"


def _daily_trend_gate(hist: pd.DataFrame | None, sma_days: int) -> int:
    """+1 = longs allowed (daily uptrend), -1 = shorts allowed, 0 = no gate data.

    Same Connors-style gate band_tag uses: compare the latest daily close to the
    sma_days-day average of daily closes.
    """
    if hist is None or hist.empty:
        return 0
    day_key = hist.index.tz_convert(ET).normalize()
    daily_close = hist.groupby(day_key)["close"].last()
    if len(daily_close) < sma_days:
        return 0
    sma = float(daily_close.tail(sma_days).mean())
    return 1 if float(daily_close.iloc[-1]) >= sma else -1


def _vwap_sigma(today: pd.DataFrame, vw: np.ndarray) -> np.ndarray:
    """Rolling volume-weighted standard deviation of price around session VWAP.

    Cumulative (session-anchored) to match the cumulative VWAP: sigma_i =
    sqrt( sum_k v_k (tp_k - vwap_i)^2 / sum_k v_k ) over k<=i. This is the dispersion
    the 2-SD reversion band is built on.
    """
    tp = ((today["high"] + today["low"] + today["close"]) / 3).to_numpy()
    vol = today["volume"].to_numpy().astype(float)
    cum_v = np.cumsum(vol)
    cum_vtp2 = np.cumsum(vol * tp * tp)
    # E[tp^2] - (E[tp])^2 ; E[tp] is the vwap itself
    with np.errstate(divide="ignore", invalid="ignore"):
        mean_tp2 = np.where(cum_v > 0, cum_vtp2 / cum_v, 0.0)
        var = mean_tp2 - vw * vw
    var = np.clip(var, 0.0, None)
    return np.sqrt(var)


def generate(
    today: pd.DataFrame,
    *,
    hist: pd.DataFrame | None = None,
    # Defaults are the tuned + out-of-sample-validated values (2026-07-21). A 60d sweep
    # over 8 core symbols, then re-checked on 8 UNSEEN symbols: RSI(14) 30/70 + 1.5 SD
    # band + 2.0 SD stop gave PF 5.39 over all 16 symbols (76% win core / 60% OOS), and
    # stayed profitable with the regime filter OFF (PF 1.77 OOS) — a plateau across every
    # single-param nudge, not an overfit spike. The original RSI(2)≤5 idea was far too
    # strict (PF 0.86); RSI(14) at 30/70 is the extreme-but-not-starved sweet spot.
    band_sigma: float = 1.5,       # tag the ±1.5 SD VWAP band
    stop_sigma: float = 2.0,       # stop beyond the ±2 SD band (target is VWAP itself)
    rsi_period: int = 14,
    rsi_lo: float = 30.0,
    rsi_hi: float = 70.0,
    sma_days: int = 10,
    min_bars_open: int = 6,        # skip first 30 min (VWAP not yet anchored)
    vol_period: int = 20,
    vol_mult: float = 1.3,         # tag bar must show >= this x avg volume
    atr_period: int = 14,
    max_per_side: int = 2,
    skip_lull: bool = True,        # skip the 11:30-14:00 ET mid-day chop
    lull_start_min: int = 120,     # minutes after open the lull begins (~11:30 ET)
    lull_end_min: int = 270,       # minutes after open the lull ends   (~14:00 ET)
    **_,
) -> list[Signal]:
    n = len(today)
    if n < max(vol_period, atr_period) + 2:
        return []

    gate = _daily_trend_gate(hist, sma_days)
    vw = vwap(today).to_numpy()
    sigma = _vwap_sigma(today, vw)
    r = rsi(today["close"], rsi_period).to_numpy()
    a = atr(today, atr_period).to_numpy()
    closes = today["close"].to_numpy()
    volumes = today["volume"].to_numpy().astype(float)
    vol_avg = pd.Series(volumes).rolling(vol_period).mean().to_numpy()

    # minutes-since-open for each bar, for the session-timing filter
    open_ts = today.index[0]
    mins = ((today.index - open_ts).total_seconds() / 60.0).to_numpy()

    out: list[Signal] = []
    n_long = n_short = 0
    start = max(vol_period, atr_period, min_bars_open)
    for i in range(start, n):
        c, v, sd, ri, ai = float(closes[i]), float(vw[i]), float(sigma[i]), float(r[i]), float(a[i])
        if sd <= 0 or ai <= 0:
            continue
        if skip_lull and lull_start_min <= float(mins[i]) <= lull_end_min:
            continue
        vi, va = float(volumes[i]), float(vol_avg[i])
        if va > 0 and vi < vol_mult * va:
            continue

        upper2 = v + band_sigma * sd
        lower2 = v - band_sigma * sd
        upper3 = v + stop_sigma * sd
        lower3 = v - stop_sigma * sd

        # Long: price stretched below the -band, RSI oversold, daily trend up.
        # Guard: only take it if the geometry is coherent — the -stop band must be below
        # the entry (a stretched-down close) and VWAP above it. Very early in the session
        # sigma is tiny and the bands can invert; those are not real stretches.
        if gate >= 0 and n_long < max_per_side and c < lower2 and ri <= rsi_lo and lower3 < c < v:
            out.append(Signal(
                index=i, side="long", entry=c, stop=lower3, target=v,
                reasons=[f"<-{band_sigma:.1f}SD VWAP", f"RSI={ri:.0f}", f"vol {vi/va:.1f}x", "daily up"],
                strategy="confluence", entry_type="limit",
            ))
            n_long += 1
        # Short: price stretched above the +band, RSI overbought, daily trend down.
        elif gate <= 0 and n_short < max_per_side and c > upper2 and ri >= rsi_hi and v < c < upper3:
            out.append(Signal(
                index=i, side="short", entry=c, stop=upper3, target=v,
                reasons=[f">+{band_sigma:.1f}SD VWAP", f"RSI={ri:.0f}", f"vol {vi/va:.1f}x", "daily down"],
                strategy="confluence", entry_type="limit",
            ))
            n_short += 1
        if n_long >= max_per_side and n_short >= max_per_side:
            break
    return out
