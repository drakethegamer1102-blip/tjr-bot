"""Unit tests proving the SMC detectors fire on known, hand-built patterns."""

import pandas as pd

from tjrbot.smc import (
    detect_structure,
    find_fvgs,
    find_sweeps,
    find_swings,
    generate_signals,
)


def make_bars(rows):
    """rows: list of (open, high, low, close)."""
    idx = pd.date_range("2026-01-02 09:30", periods=len(rows), freq="5min")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000
    return df


def test_find_swings_high():
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (100, 102, 99.5, 101),
            (101, 105, 100.5, 104),  # clear swing high at index 2
            (104, 103.5, 102, 103),
            (103, 103, 101, 101.5),
        ]
    )
    highs = [s for s in find_swings(bars, strength=2) if s.kind == "high"]
    assert any(s.index == 2 and s.price == 105 for s in highs)


def test_find_fvgs_bullish():
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (101, 104, 100, 103),  # strong up candle
            (104, 106, 103, 105),  # low(103) > high two bars back (101) -> gap
        ]
    )
    fvgs = find_fvgs(bars, atr_mult=0.25, atr_period=14)
    assert len(fvgs) == 1
    f = fvgs[0]
    assert f.direction == 1 and f.index == 2
    assert f.top == 103 and f.bottom == 101


def test_find_sweeps_bullish():
    bars = make_bars([(100, 101, 98, 100.5)])  # wick to 98, close back above 100
    sweeps = find_sweeps(bars, levels=[100.0])
    assert len(sweeps) == 1
    assert sweeps[0].direction == 1 and sweeps[0].level == 100.0


def test_detect_structure_mss_up():
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (100, 102, 99, 101),
            (101, 105, 100, 104),  # swing high 105
            (104, 103, 101, 102),
            (102, 103, 101, 102),
            (103, 107, 102, 106),  # close 106 > 105 -> bullish MSS
        ]
    )
    events = detect_structure(bars, strength=2)
    assert any(e.kind == "MSS" and e.bias == 1 and e.index == 5 for e in events)


def test_generate_signals_long():
    bars = make_bars(
        [
            (100, 101, 99, 100),  # 0
            (100, 102, 99.5, 101),  # 1
            (101, 105, 100.5, 104),  # 2  swing high 105 (the level MSS must break)
            (104, 103.5, 102, 103),  # 3
            (103, 103, 101, 101.5),  # 4
            (101.5, 102, 100.5, 101),  # 5
            (101, 101.5, 100.2, 100.5),  # 6
            (100.5, 100.8, 99, 99.5),  # 7
            (99.5, 101, 98.5, 100.7),  # 8  bullish sweep of 100 (wick 98.5, close 100.7)
            (100.7, 103, 100.5, 102.8),  # 9
            (103, 104, 102.7, 103.8),  # 10
            (105, 107, 104, 106),  # 11 close>105 (MSS up) AND low(104)>high[9](103) -> FVG
        ]
    )
    signals = generate_signals(
        bars, levels=[100.0], pivot_strength=2, confirm_window=10, min_rr=2.0
    )
    longs = [s for s in signals if s.side == "long"]
    assert len(longs) >= 1
    s = longs[0]
    assert abs(s.stop - 98.5) < 1e-9  # stop below the swept low
    assert s.entry == 103.0  # enter at the bottom of the FVG (high of bar 9)
    assert s.target > s.entry  # long target is above entry
