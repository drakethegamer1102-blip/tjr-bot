"""Tests for the daily-bias and session filters."""

import pandas as pd

from tjrbot.smc.session import in_session
from tjrbot.strategy import daily_bias


def make_bars(rows):
    idx = pd.date_range("2026-01-02 09:30", periods=len(rows), freq="5min")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000
    return df


def test_daily_bias_bullish():
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (100, 102, 99, 101),
            (101, 105, 100, 104),  # swing high 105
            (104, 103, 101, 102),
            (102, 103, 101, 102),
            (103, 107, 102, 106),  # close > 105 -> bullish MSS
        ]
    )
    assert daily_bias(bars, strength=2) == 1


def test_session_filter():
    rth_time = pd.Timestamp("2026-01-05 10:00", tz="America/New_York")
    after_hours = pd.Timestamp("2026-01-05 17:00", tz="America/New_York")
    assert in_session(rth_time, ["rth"]) is True
    assert in_session(rth_time, ["ny_open"]) is True
    assert in_session(after_hours, ["rth"]) is False
