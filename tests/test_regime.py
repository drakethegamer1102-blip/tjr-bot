"""Tests for the trend/regime filter."""

import pandas as pd

from tjrbot.regime import filter_signals, market_bias, market_filter, trend_at
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


# ── market breadth filter (the 2026-06-18 fix) ───────────────────────────────
def test_market_bias_risk_on():
    # Index opens 100, climbs to ~103 (close above open and above VWAP) -> +1
    rows = [(100 + i * 0.1, 100 + i * 0.1 + 0.2, 100 + i * 0.1 - 0.2, 100 + i * 0.1) for i in range(30)]
    assert market_bias(make_day(rows)) == 1


def test_market_bias_risk_off():
    rows = [(110 - i * 0.1, 110 - i * 0.1 + 0.2, 110 - i * 0.1 - 0.2, 110 - i * 0.1) for i in range(30)]
    assert market_bias(make_day(rows)) == -1


def test_market_bias_flat_is_neutral():
    rows = [(100, 100.3, 99.7, 100 + (0.05 if i % 2 else -0.05)) for i in range(30)]
    assert market_bias(make_day(rows)) == 0


def test_market_filter_blocks_shorts_on_risk_on_day():
    # This is the TSLA/MSFT case: counter-market short must be dropped, long kept.
    sigs = [
        Signal(20, "short", 400, 402, 396, strategy="tjr"),
        Signal(20, "long", 400, 398, 404, strategy="momentum"),
    ]
    kept = market_filter(sigs, market_bias_value=1)
    assert len(kept) == 1 and kept[0].side == "long"


def test_market_filter_blocks_longs_on_risk_off_day():
    sigs = [Signal(20, "long", 400, 398, 404, strategy="momentum")]
    assert market_filter(sigs, market_bias_value=-1) == []


def test_market_filter_noop_when_neutral():
    sigs = [Signal(20, "short", 400, 402, 396), Signal(20, "long", 400, 398, 404)]
    assert len(market_filter(sigs, market_bias_value=0)) == 2


def test_trend_at_strong_adx_not_neutral():
    # A clean strong uptrend: trend_at must flag +1 (2-of-3 majority), never 0.
    rows = [(100 + i, 100 + i + 0.5, 100 + i - 0.5, 100 + i) for i in range(30)]
    today = make_day(rows)
    assert trend_at(today, 29) == 1
