"""Tests for the trend/regime filter."""

import pandas as pd

from tjrbot.regime import filter_signals, trend_at
from tjrbot.smc.signals import Signal


def make_day(rows):
    idx = pd.date_range("2026-06-11 09:30", periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000
    return df


def test_uptrend_blocks_shorts_allows_longs():
    rows = [(100 + i, 100 + i + 0.5, 100 + i - 0.5, 100 + i) for i in range(30)]  # steady up
    today = make_day(rows)
    assert trend_at(today, 29) == 1
    sigs = [
        Signal(29, "short", 129, 130, 127, strategy="vwap_rev"),
        Signal(29, "long", 129, 128, 131, strategy="momentum"),
    ]
    kept = filter_signals(sigs, today)
    assert len(kept) == 1 and kept[0].side == "long"  # the counter-trend short is dropped


def test_downtrend_blocks_longs():
    rows = [(130 - i, 130 - i + 0.5, 130 - i - 0.5, 130 - i) for i in range(30)]  # steady down
    today = make_day(rows)
    assert trend_at(today, 29) == -1
    kept = filter_signals([Signal(29, "long", 100, 99, 103)], today)
    assert kept == []


def test_range_allows_both():
    rows = [(100, 100.5, 99.5, 100 + (0.3 if i % 2 else -0.3)) for i in range(30)]  # flat chop
    today = make_day(rows)
    assert trend_at(today, 29) == 0
    sigs = [Signal(29, "short", 100, 101, 98), Signal(29, "long", 100, 99, 102)]
    assert len(filter_signals(sigs, today)) == 2
