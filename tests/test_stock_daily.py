"""Tests for the 3 new daily stock strategies (DIPSNAP / PULLBACK / TUESDAY-EQ)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tjrbot.strategies import stock_daily as sd


def _daily(closes, lows=None, start="2024-01-01"):
    n = len(closes)
    idx = pd.date_range(start, periods=n, freq="B")
    lows = lows or [c - 1 for c in closes]
    return pd.DataFrame({"open": closes, "high": [c + 1 for c in closes],
                         "low": lows, "close": closes}, index=idx)


def test_dipsnap_fires_on_oversold_uptrend():
    # steady uptrend then a sharp multi-day drop -> RSI2 collapses but still above 200 SMA
    closes = list(np.linspace(3000, 5000, 205)) + [4980, 4950, 4900, 4850, 4820]
    plan = sd.dipsnap(_daily(closes))
    assert plan and plan["name"] == "DIPSNAP"


def test_dipsnap_silent_below_200sma():
    closes = list(np.linspace(5000, 3000, 205)) + [2990, 2980, 2970, 2960, 2950]  # downtrend
    assert sd.dipsnap(_daily(closes)) is None


def test_pullback_fires_on_10d_low_in_golden_uptrend():
    closes = list(np.linspace(3000, 5000, 210)) + [4900]
    lows = [c - 1 for c in closes]
    lows[-1] = min(lows[-11:-1]) - 5
    df = _daily(closes, lows=lows)
    df.loc[df.index[-1], "close"] = df["low"].iloc[-1] + 0.5
    plan = sd.pullback(df)
    assert plan and plan["name"] == "PULLBACK"


def test_pullback_silent_in_downtrend():
    closes = list(np.linspace(5000, 3000, 210))
    assert sd.pullback(_daily(closes)) is None


def test_tuesday_eq_fires_when_monday_down():
    idx = pd.date_range("2024-01-01", periods=6, freq="B")
    closes = [100, 101, 102, 103, 101, 100]
    df = pd.DataFrame({"open": closes, "high": [c+1 for c in closes],
                       "low": [c-1 for c in closes], "close": closes}, index=idx)
    assert df.index[-1].weekday() == 0
    plan = sd.tuesday_eq(df)
    assert plan and plan["name"] == "TUESDAY-EQ"


def test_rsi2_helper_extremes():
    falling = pd.Series(list(range(100, 80, -1)), dtype=float)   # steadily down -> low RSI2
    rising = pd.Series(list(range(80, 100)), dtype=float)        # steadily up -> high RSI2
    assert sd._rsi2(falling) < 20
    assert sd._rsi2(rising) > 80


def test_registry_and_isolation():
    assert set(sd.REGISTRY) == {"DIPSNAP", "PULLBACK", "TUESDAY-EQ"}
    from tjrbot.strategies.futures_daily import REGISTRY as F1
    from tjrbot.strategies.futures_daily_v2 import REGISTRY as F2
    assert not (set(sd.REGISTRY) & (set(F1) | set(F2)))
