"""Tests for the ORB and VWAP-reversion strategies."""

import pandas as pd

from tjrbot.strategies import orb, vwap_rev


def make_day(rows, start="2026-06-10 09:30"):
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000
    return df


def test_orb_long_breakout():
    bars = make_day(
        [
            (100, 101, 99, 100),       # 9:30 opening range
            (100, 101, 99.5, 100.5),   # 9:35 opening range
            (100.5, 101, 100, 100.8),  # 9:40 opening range (ends 9:45: ORH=101, ORL=99)
            (100.8, 102.5, 100.7, 102.2),  # 9:45 breakout: close 102.2 > 101 and > VWAP
            (102.2, 103, 101.5, 102.5),
        ]
    )
    sigs = orb.generate(bars, or_minutes=15, min_rr=2.0)
    longs = [s for s in sigs if s.side == "long"]
    assert len(longs) >= 1
    s = longs[0]
    assert s.index == 3 and abs(s.stop - 99.0) < 1e-9
    assert s.strategy == "orb" and s.entry_type == "market"


def test_vwap_rev_short_on_overstretch():
    # steep ramp up -> RSI high and price far above VWAP -> fade short
    rows = [(100 + 2 * i, 100 + 2 * i + 0.5, 100 + 2 * i - 0.5, 100 + 2 * i) for i in range(20)]
    sigs = vwap_rev.generate(make_day(rows), atr_mult=1.0, rsi_hi=60, rsi_period=14)
    shorts = [s for s in sigs if s.side == "short"]
    assert len(shorts) >= 1
    assert shorts[0].strategy == "vwap_rev" and shorts[0].entry_type == "market"
