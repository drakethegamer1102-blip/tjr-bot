"""Tests for the 3 new daily futures strategies (TUESDAY / CAPITULATION / DIPBUYER)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tjrbot.strategies import futures_daily_v2 as v2


def _daily(closes, lows=None, start="2024-01-01"):
    n = len(closes)
    idx = pd.date_range(start, periods=n, freq="B")   # business days
    lows = lows or [c - 1 for c in closes]
    return pd.DataFrame({"open": closes, "high": [c + 1 for c in closes],
                         "low": lows, "close": closes}, index=idx)


def test_tuesday_fires_when_monday_down():
    # build so the LAST bar is a Monday that closed down
    idx = pd.date_range("2024-01-01", periods=6, freq="B")  # Mon..Mon
    closes = [100, 101, 102, 103, 101, 100]                 # last two business days
    df = pd.DataFrame({"open": closes, "high": [c+1 for c in closes],
                       "low": [c-1 for c in closes], "close": closes}, index=idx)
    # ensure last index is a Monday and it's down vs prior
    assert df.index[-1].weekday() == 0
    plan = v2.tuesday(df)
    assert plan and plan["name"] == "TUESDAY"


def test_tuesday_silent_on_non_monday():
    idx = pd.date_range("2024-01-02", periods=4, freq="B")  # Tue..Fri
    closes = [100, 99, 98, 97]
    df = pd.DataFrame({"open": closes, "high": [c+1 for c in closes],
                       "low": [c-1 for c in closes], "close": closes}, index=idx)
    assert df.index[-1].weekday() != 0
    assert v2.tuesday(df) is None


def test_capitulation_fires_on_big_drop():
    closes = [100, 100, 100, 98.0]     # last day -2% vs prior
    plan = v2.capitulation(_daily(closes))
    assert plan and plan["name"] == "CAPITULATION"


def test_capitulation_silent_on_small_drop():
    closes = [100, 100, 100, 99.5]     # -0.5%, under the 1.5% threshold
    assert v2.capitulation(_daily(closes)) is None


def test_dipbuyer_fires_on_10day_low_in_uptrend():
    # steady uptrend (50>200) then a fresh 10-day low on the last bar
    closes = list(np.linspace(3000, 5000, 210)) + [4900]     # last bar dips below recent lows
    lows = [c - 1 for c in closes]
    lows[-1] = min(lows[-11:-1]) - 5                          # force a genuine 10-day low
    df = _daily(closes, lows=lows)
    df.loc[df.index[-1], "close"] = df["low"].iloc[-1] + 0.5  # close at the low
    plan = v2.dipbuyer(df)
    assert plan and plan["name"] == "DIPBUYER"


def test_dipbuyer_silent_in_downtrend():
    closes = list(np.linspace(5000, 3000, 210))              # downtrend: 50 < 200
    assert v2.dipbuyer(_daily(closes)) is None


def test_registry_and_isolation():
    assert set(v2.REGISTRY) == {"TUESDAY", "CAPITULATION", "DIPBUYER"}
    # must not collide with the original futures_daily registry
    from tjrbot.strategies.futures_daily import REGISTRY as R1
    assert not (set(v2.REGISTRY) & set(R1))
