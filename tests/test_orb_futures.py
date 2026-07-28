"""Tests for the ORB FUTURES strategy — the futures-specific mechanics on top of ORB."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tjrbot.strategies import orb_futures
from tjrbot.strategies.orb_futures import contracts_for, MES_TICK_SIZE, MES_POINT_VALUE


def _trending_up_session():
    idx = pd.date_range("2026-07-27 09:30", periods=40, freq="5min", tz="America/New_York")
    price = np.r_[np.full(3, 5000.0), np.linspace(5000, 5040, 37)]  # MES-scale prices
    return pd.DataFrame({"open": price, "high": price + 1.0, "low": price - 1.0,
                         "close": price, "volume": 1_000}, index=idx)


def test_generates_long_on_trend_break():
    sigs = orb_futures.generate(_trending_up_session())
    assert sigs, "expected a signal on a clean upside break"
    assert sigs[0].side == "long"
    assert sigs[0].strategy == "orb_futures"


def test_prices_are_on_the_tick_grid():
    sigs = orb_futures.generate(_trending_up_session())
    s = sigs[0]
    for px in (s.entry, s.stop, s.target):
        # every price must be an exact multiple of the tick size (0.25 for MES)
        assert abs(round(px / MES_TICK_SIZE) * MES_TICK_SIZE - px) < 1e-9, f"{px} off tick grid"


def test_target_respects_reward_risk():
    sigs = orb_futures.generate(_trending_up_session())
    s = sigs[0]
    risk = s.entry - s.stop
    reward = s.target - s.entry
    assert risk > 0
    assert reward >= 1.9 * risk  # ~2:1 (allow tick rounding slack)


def test_min_stop_ticks_floor():
    # a break only 1 tick above the range should still get a stop >= min_stop_ticks away
    idx = pd.date_range("2026-07-27 09:30", periods=10, freq="5min", tz="America/New_York")
    # flat range then a 1-tick pop above
    close = np.array([5000, 5000, 5000, 5000.25, 5000.25, 5000.25, 5000.25, 5000.25, 5000.25, 5000.25])
    df = pd.DataFrame({"open": close, "high": close + 0.25, "low": close - 0.25,
                       "close": close, "volume": 1_000}, index=idx)
    sigs = orb_futures.generate(df, min_stop_ticks=8, vwap_confirm=False)
    if sigs:  # if it fires, the stop must honor the tick floor
        s = sigs[0]
        assert s.entry - s.stop >= 8 * MES_TICK_SIZE - 1e-9


def test_contract_sizing_dollar_risk():
    # 50k account, 1% risk = $500. Entry 5000, stop 4996 -> 4 points = $20/contract -> 25 contracts,
    # but max_contracts caps it.
    n = contracts_for(50_000, 5000.0, 4996.0, risk_fraction=0.01, max_contracts=10)
    assert n == 10  # capped
    # wider stop -> fewer contracts, uncapped path
    n2 = contracts_for(50_000, 5000.0, 4980.0, risk_fraction=0.01, max_contracts=50)
    # 20 points * $5 = $100/contract; $500/$100 = 5
    assert n2 == 5


def test_zero_risk_sizes_to_zero():
    assert contracts_for(50_000, 5000.0, 5000.0) == 0


def test_leaves_stock_orb_untouched_signature():
    # sanity: the futures module is a separate object from stock orb
    from tjrbot.strategies import orb
    assert orb.generate is not orb_futures.generate
