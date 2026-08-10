"""Tests for the 3 new daily crypto strategies (MOONSHOT / CRYPTODIP / CRYPTORSI)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tjrbot.strategies import crypto_daily as cd


def _daily(closes, highs=None, lows=None):
    n = len(closes)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")   # crypto = every day
    return pd.DataFrame({"open": closes,
                         "high": highs or [c + 1 for c in closes],
                         "low": lows or [c - 1 for c in closes],
                         "close": closes}, index=idx)


def test_moonshot_fires_on_20d_high_breakout():
    # steady uptrend so a fresh high also sits above the 200d SMA
    closes = list(np.linspace(20000, 60000, 210)) + [61000]
    highs = [c + 10 for c in closes]
    highs[-1] = max(highs[-21:-1]) + 100        # genuine 20-day high
    df = _daily(closes, highs=highs)
    df.loc[df.index[-1], "close"] = df["high"].iloc[-1]
    plan = cd.moonshot(df)
    assert plan and plan["name"] == "MOONSHOT"


def test_moonshot_silent_below_200sma():
    closes = list(np.linspace(60000, 20000, 210)) + [20500]   # downtrend
    assert cd.moonshot(_daily(closes)) is None


def test_cryptodip_fires_on_10d_low_in_uptrend():
    closes = list(np.linspace(20000, 60000, 210)) + [58000]
    lows = [c - 10 for c in closes]
    lows[-1] = min(lows[-11:-1]) - 100
    df = _daily(closes, lows=lows)
    df.loc[df.index[-1], "close"] = df["low"].iloc[-1] + 5
    plan = cd.cryptodip(df)
    assert plan and plan["name"] == "CRYPTODIP"


def test_cryptorsi_fires_when_oversold_in_uptrend():
    closes = list(np.linspace(20000, 60000, 205)) + [59000, 58000, 57000, 56000, 55000]
    plan = cd.cryptorsi(_daily(closes))
    assert plan and plan["name"] == "CRYPTORSI"


def test_cryptorsi_silent_in_downtrend():
    closes = list(np.linspace(60000, 20000, 205)) + [20900, 20800, 20700, 20600, 20500]
    assert cd.cryptorsi(_daily(closes)) is None


def test_registry_and_isolation():
    assert set(cd.REGISTRY) == {"MOONSHOT", "CRYPTODIP", "CRYPTORSI"}
    from tjrbot.strategies.futures_daily import REGISTRY as F1
    from tjrbot.strategies.stock_daily import REGISTRY as S1
    assert not (set(cd.REGISTRY) & (set(F1) | set(S1)))
