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


def test_vwap_rev_long_fires_on_oversold_stretch():
    """A decline stretching >atr_mult*ATR below VWAP with weak RSI must fire a long.
    (Rewritten 2026-07-09: the old test contorted itself around the EMA-alignment
    gate, which was removed — it contradicted the stretch condition and produced
    ZERO trades in 60 days. Counter-trend protection now lives in regime.filter_signals.)"""
    rows = []
    # bars 0-14: flat at 115 — VWAP and averages anchor high
    for _ in range(15):
        rows.append((115, 115.5, 114.5, 115))
    # bars 15-20: steady decline to 109 — close stretches below VWAP, RSI sinks
    for i in range(6):
        p = 114 - i
        rows.append((p + 0.3, p + 0.5, p - 0.5, p))
    sigs = vwap_rev.generate(
        make_day(rows),
        atr_mult=0.5,
        rsi_lo=50,
        rsi_period=10,
        min_bars_open=0,
        vol_period=5,
        vol_mult=0,  # synthetic bars have flat volume; disable filter in unit tests
    )
    longs = [s for s in sigs if s.side == "long"]
    assert len(longs) >= 1, "expected long on an oversold stretch below VWAP"
    s = longs[0]
    assert s.strategy == "vwap_rev" and s.entry_type == "market"
    assert s.target > s.entry, "target must be VWAP, above the stretched-down entry"


def test_vwap_rev_regime_filter_blocks_counter_trend():
    """In a strong monotonic uptrend the raw strategy may emit a short (RSI pinned
    high, price stretched over VWAP) — the engine-side regime filter must drop it.
    This is the protection that replaced the removed EMA gate."""
    from tjrbot.regime import filter_signals

    rows = [(100 + 2 * i, 100 + 2 * i + 0.5, 100 + 2 * i - 0.5, 100 + 2 * i) for i in range(25)]
    day = make_day(rows)
    sigs = vwap_rev.generate(
        day, atr_mult=0.5, rsi_hi=55, rsi_period=14, min_bars_open=0, vol_period=5, vol_mult=0
    )
    shorts = [s for s in sigs if s.side == "short"]
    assert len(shorts) >= 1, "raw strategy should emit a short in this stretch (pre-filter)"
    kept = filter_signals(sigs, day)
    assert not [s for s in kept if s.side == "short"], (
        "regime filter must block shorts in a strong uptrend"
    )


def test_vwap_rev_min_bars_open():
    rows = [(100 + 2*i, 100 + 2*i + 0.5, 100 + 2*i - 0.5, 100 + 2*i) for i in range(25)]
    sigs = vwap_rev.generate(
        make_day(rows), atr_mult=0.5, rsi_hi=50, rsi_period=14, ema_period=10, min_bars_open=99, vol_mult=0
    )
    assert len(sigs) == 0, "min_bars_open=99 must suppress all signals"
