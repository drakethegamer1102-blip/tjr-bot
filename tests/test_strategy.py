"""Tests for the daily-bias and session filters."""

import pandas as pd

from tjrbot.smc.session import in_session
from tjrbot.strategy import daily_bias


def make_bars(rows):
    idx = pd.date_range("2026-01-02 09:30", periods=len(rows), freq="5min")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000
    return df


def _staircase(up: bool):
    """A clean HH+HL (up) or LH+LL (down) staircase: alternating swing highs/lows
    that each step in the trend direction, so both the swing-sequence read and the
    net-of-structure-events read agree."""
    rows = []
    base = 100.0
    step = 4.0 if up else -4.0
    # pivots need `strength` bars of padding each side; build clear alternating swings
    pivots = [base, base - 2, base + step, base + step - 2,
              base + 2 * step, base + 2 * step - 2, base + 3 * step]
    for i, p in enumerate(pivots):
        # pad each pivot with two lower (or surrounding) bars so find_swings confirms it
        rows.append((p - 1, p - 0.5, p - 1.5, p - 1))
        rows.append((p - 0.5, p + 0.5, p - 0.8, p))      # the pivot bar (local extreme)
        rows.append((p - 1, p - 0.5, p - 1.5, p - 1))
    return make_bars(rows)


def test_daily_bias_bullish():
    # Robust read: needs a real HH+HL sequence, not a single MSS on a thin sample.
    assert daily_bias(_staircase(up=True), strength=1) == 1


def test_daily_bias_bearish():
    assert daily_bias(_staircase(up=False), strength=1) == -1


def test_daily_bias_neutral_on_thin_sample():
    # A 6-bar window is too thin to read a trend (needs strength*4+6 bars) -> neutral
    # (trade both sides), NOT a forced directional bias. This is the June-11 fix:
    # a noisy/short HTF must never lock the bot into one direction.
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (100, 102, 99, 101),
            (101, 105, 100, 104),
            (104, 103, 101, 102),
            (102, 103, 101, 102),
            (103, 107, 102, 106),
        ]
    )
    assert daily_bias(bars, strength=2) == 0


def test_session_filter():
    rth_time = pd.Timestamp("2026-01-05 10:00", tz="America/New_York")
    after_hours = pd.Timestamp("2026-01-05 17:00", tz="America/New_York")
    assert in_session(rth_time, ["rth"]) is True
    assert in_session(rth_time, ["ny_open"]) is True
    assert in_session(after_hours, ["rth"]) is False
