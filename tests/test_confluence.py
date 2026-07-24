"""Tests for the merged 'confluence' VWAP-reversion strategy (2026-07-21)."""

import numpy as np
import pandas as pd

from tjrbot.strategies import confluence


ET = "America/New_York"


def make_day(rows, start="2026-06-10 09:30", volume=1000):
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz=ET)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = volume
    return df


def make_hist(last_close, sma_below, days=12):
    """Daily-ish hist whose last daily close is above (sma_below=False) or below
    (sma_below=True) its own sma_days average — drives the trend gate."""
    # one bar per day at 16:00 ET; earlier days sit at a baseline, last day set explicitly
    base = last_close + (5 if sma_below else -5)  # prior days above/below to push the SMA
    rows, idx = [], []
    for d in range(days):
        day = pd.Timestamp("2026-06-01 16:00", tz=ET) + pd.Timedelta(days=d)
        close = last_close if d == days - 1 else base
        rows.append((close, close, close, close))
        idx.append(day)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=pd.DatetimeIndex(idx))
    df["volume"] = 1000
    return df


def _oversold_day():
    """A choppy anchor (builds real VWAP dispersion / sigma), then a single sharp
    down-close that lands BETWEEN the -1SD and -2SD bands with RSI(14) sinking — a
    coherent long fade (below the entry band, still above the stop band)."""
    rows = []
    for i in range(24):
        p = 115 + (2 if i % 2 == 0 else -2)           # oscillate to build sigma (~2.0)
        rows.append((p, p + 0.5, p - 0.5, p))
    rows.append((113, 113, 111.5, 111.7))             # the stretched-down tag bar
    return make_day(rows)


def test_confluence_long_fires_on_oversold_stretch_with_daily_uptrend():
    day = _oversold_day()
    hist = make_hist(last_close=115, sma_below=False)  # daily UPtrend -> longs allowed
    sigs = confluence.generate(
        day, hist=hist,
        band_sigma=1.0, stop_sigma=2.0, rsi_period=14, rsi_lo=45, rsi_hi=55,
        min_bars_open=0, vol_mult=0, skip_lull=False,
    )
    longs = [s for s in sigs if s.side == "long"]
    assert len(longs) >= 1, "expected a long on the oversold sub-VWAP stretch"
    s = longs[0]
    assert s.strategy == "confluence"
    assert s.entry_type == "limit", "confluence must use latency-safe limit entries"
    assert s.target > s.entry, "target is VWAP, which sits above the stretched-down entry"
    assert s.stop < s.entry, "long stop sits below entry (beyond the -SD band)"


def test_confluence_daily_gate_blocks_counter_trend_long():
    """Same oversold day, but the daily trend is DOWN -> the gate must block the long
    (don't catch a falling knife against the higher-timeframe trend)."""
    day = _oversold_day()
    hist = make_hist(last_close=115, sma_below=True)   # daily DOWNtrend -> longs blocked
    sigs = confluence.generate(
        day, hist=hist,
        band_sigma=1.0, stop_sigma=2.0, rsi_period=14, rsi_lo=45, rsi_hi=55,
        min_bars_open=0, vol_mult=0, skip_lull=False,
    )
    assert not [s for s in sigs if s.side == "long"], "daily downtrend must block the long"


def test_confluence_volume_filter_blocks_thin_stretch():
    """With a strict volume filter and flat (thin) volume, nothing should fire."""
    day = _oversold_day()  # flat volume everywhere
    hist = make_hist(last_close=115, sma_below=False)
    sigs = confluence.generate(
        day, hist=hist,
        band_sigma=1.0, stop_sigma=2.0, rsi_period=14, rsi_lo=45, rsi_hi=55,
        min_bars_open=0, vol_mult=5.0, skip_lull=False,  # demand 5x avg vol -> never met
    )
    assert not sigs, "thin-volume stretch must be filtered out"


def test_confluence_no_gate_data_allows_both_sides():
    """With no hist (gate==0) the strategy still runs (gate is permissive, not blocking)."""
    day = _oversold_day()
    sigs = confluence.generate(
        day, hist=None,
        band_sigma=1.0, stop_sigma=2.0, rsi_period=14, rsi_lo=45, rsi_hi=55,
        min_bars_open=0, vol_mult=0, skip_lull=False,
    )
    assert [s for s in sigs if s.side == "long"], "no gate data should not block valid setups"
