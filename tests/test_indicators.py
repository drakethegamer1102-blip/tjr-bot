"""Tests for the technical indicators."""

import pandas as pd

from tjrbot.indicators import ema, rsi, vwap


def test_ema_constant():
    s = pd.Series([5.0] * 10)
    assert abs(ema(s, 3).iloc[-1] - 5.0) < 1e-9


def test_rsi_uptrend_high():
    s = pd.Series([float(i) for i in range(1, 30)])  # monotonic up
    assert rsi(s, 14).iloc[-1] > 70


def test_rsi_downtrend_low():
    s = pd.Series([float(30 - i) for i in range(1, 30)])  # monotonic down
    assert rsi(s, 14).iloc[-1] < 30


def test_vwap_equal_volume():
    # equal volume -> VWAP equals the running mean of the typical price
    bars = pd.DataFrame(
        {"high": [10, 12, 14], "low": [8, 10, 12], "close": [9, 11, 13], "volume": [100, 100, 100]}
    )
    # typical = 9, 11, 13 -> cumulative mean = 9, 10, 11
    assert abs(vwap(bars).iloc[-1] - 11.0) < 1e-9
