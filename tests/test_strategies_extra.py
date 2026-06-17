"""Tests for the bollinger_rev / macd_trend / squeeze_breakout strategies and the
indicators they depend on (tjrbot.indicators_extra)."""

import numpy as np
import pandas as pd

from tjrbot.indicators_extra import bollinger, keltner, macd
from tjrbot.strategies import bollinger_rev, macd_trend, squeeze_breakout


def make_day(rows, start="2026-06-10 09:30", volume=1000):
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = volume
    return df


# ── indicators ──────────────────────────────────────────────────────────────
def test_bollinger_order_and_values():
    s = pd.Series([10.0] * 25)  # flat -> std 0, bands collapse onto middle
    mid, upper, lower = bollinger(s, period=20, num_std=2.0)
    assert mid.iloc[-1] == 10.0
    # bands are symmetric around middle and ordered lower <= middle <= upper
    assert lower.iloc[-1] <= mid.iloc[-1] <= upper.iloc[-1]


def test_bollinger_band_widths():
    s = pd.Series(np.linspace(100, 120, 30))
    mid, upper, lower = bollinger(s, period=20, num_std=2.0)
    # upper-mid should equal mid-lower (symmetric), and be positive on a moving series
    assert abs((upper.iloc[-1] - mid.iloc[-1]) - (mid.iloc[-1] - lower.iloc[-1])) < 1e-9
    assert upper.iloc[-1] > mid.iloc[-1]


def test_macd_order_and_crossover_sign():
    # rising series -> macd_line eventually > 0
    s = pd.Series(np.linspace(100, 140, 60))
    macd_line, signal_line, hist = macd(s)
    assert macd_line.iloc[-1] > 0
    assert abs(hist.iloc[-1] - (macd_line.iloc[-1] - signal_line.iloc[-1])) < 1e-9


def test_keltner_order():
    bars = make_day([(100, 101, 99, 100)] * 30)
    mid, upper, lower = keltner(bars, period=20, atr_mult=1.5)
    assert lower.iloc[-1] <= mid.iloc[-1] <= upper.iloc[-1]


# ── invariant: no strategy ever emits an inverted trade ─────────────────────
def _assert_valid(sigs):
    for s in sigs:
        if s.side == "long":
            assert s.stop < s.entry < s.target, f"inverted long: {s}"
        else:
            assert s.stop > s.entry > s.target, f"inverted short: {s}"


def test_no_inverted_trades_on_noisy_data():
    rng = np.random.default_rng(42)
    price = 100 + np.cumsum(rng.normal(0, 0.5, 120))
    rows = [(p, p + 0.3, p - 0.3, p) for p in price]
    day = make_day(rows, volume=2000)
    for gen in (bollinger_rev.generate, macd_trend.generate, squeeze_breakout.generate):
        sigs = gen(day)
        _assert_valid(sigs)
        # at most one long and one short per session
        assert sum(s.side == "long" for s in sigs) <= 1
        assert sum(s.side == "short" for s in sigs) <= 1


# ── targeted trigger tests ──────────────────────────────────────────────────
def test_bollinger_rev_long_on_oversold_dip():
    # 22 flat bars at 100 (mid≈100), then a sharp dip below the lower band w/ low RSI
    rows = [(100, 100.3, 99.7, 100)] * 22
    rows += [(100, 100, 95.0, 95.0)]   # close 95 << lower band, RSI crashes
    day = make_day(rows)
    sigs = bollinger_rev.generate(day, rsi_lo=40.0)
    longs = [s for s in sigs if s.side == "long"]
    assert len(longs) == 1
    assert longs[0].strategy == "bollinger_rev"
    assert longs[0].target > longs[0].entry      # target = middle band, above entry
    _assert_valid(sigs)


def test_macd_trend_warmup_guard():
    # too few bars -> no signals, no error
    day = make_day([(100, 101, 99, 100)] * 10)
    assert macd_trend.generate(day) == []


def test_squeeze_breakout_needs_volume_surge():
    # Flat then volatile, but volume never surges -> no breakout (volume gate)
    rows = [(100, 100.2, 99.8, 100)] * 22 + [(100, 103, 100, 103)]
    day = make_day(rows, volume=1000)  # constant volume -> vol[i] !> 1.2*avg
    sigs = squeeze_breakout.generate(day)
    assert sigs == []
