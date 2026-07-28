"""Tests for the real-time current-bar append (all strategies see price up to NOW)."""

from __future__ import annotations

import pandas as pd

from tjrbot.data.alpaca_data import _append_realtime_bar
from alpaca.data.enums import DataFeed


class _Trade:
    def __init__(self, price, ts):
        self.price = price; self.timestamp = ts


class _Client:
    """Fake client returning a canned latest trade."""
    def __init__(self, price, ts):
        self._t = _Trade(price, ts)
    def get_stock_latest_trade(self, req):
        return {"SPY": self._t}


class _BrokenClient:
    def get_stock_latest_trade(self, req):
        raise RuntimeError("feed down")


def _df():
    idx = pd.date_range("2026-07-28 15:00", periods=3, freq="5min", tz="UTC")
    return pd.DataFrame({"open": [500, 501, 502], "high": [500.5, 501.5, 502.5],
                         "low": [499.5, 500.5, 501.5], "close": [501, 502, 503],
                         "volume": [1e6] * 3}, index=idx)


def test_append_adds_forming_bar_when_trade_is_newer():
    df = _df()
    ts = pd.Timestamp("2026-07-28 15:22", tz="UTC")   # after the last 15:10 bar
    out = _append_realtime_bar(df.copy(), _Client(510.0, ts), "SPY", "5Min", DataFeed.IEX)
    assert len(out) == len(df) + 1
    assert out.index[-1] == pd.Timestamp("2026-07-28 15:20", tz="UTC")  # floored to 5-min
    assert float(out["close"].iloc[-1]) == 510.0


def test_append_updates_last_bar_when_trade_inside_it():
    df = _df()
    ts = pd.Timestamp("2026-07-28 15:12", tz="UTC")   # inside the last 15:10 bar
    out = _append_realtime_bar(df.copy(), _Client(505.0, ts), "SPY", "5Min", DataFeed.IEX)
    assert len(out) == len(df)                          # no new row
    assert float(out["close"].iloc[-1]) == 505.0        # close updated to live price
    assert float(out["high"].iloc[-1]) == 505.0         # high bumped (505 > 502.5)


def test_append_fails_open_on_error():
    df = _df()
    out = _append_realtime_bar(df.copy(), _BrokenClient(), "SPY", "5Min", DataFeed.IEX)
    assert out.equals(df)                               # unchanged, never raises


def test_append_noop_on_empty_df():
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    ts = pd.Timestamp("2026-07-28 15:22", tz="UTC")
    out = _append_realtime_bar(empty, _Client(510.0, ts), "SPY", "5Min", DataFeed.IEX)
    assert out.empty
