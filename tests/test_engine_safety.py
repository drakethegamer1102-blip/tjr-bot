"""Tests for the engine's overnight-risk safety logic: the widened EOD flatten
window and the stale-position backstop. These guard the bug where a 06-16 ARM short
went overnight unprotected and lost ~$507."""

import datetime as dt
from zoneinfo import ZoneInfo

import tjrbot.engine as engine

ET = ZoneInfo("America/New_York")


class FakePos:
    def __init__(self, symbol, qty=10, side="long"):
        self.symbol = symbol
        self.qty = str(qty)
        self.side = side


class FakeBroker:
    """Minimal broker double: records close calls."""
    def __init__(self, positions, opened_today=None):
        self._positions = positions
        self._opened_today = opened_today or {}
        self.closed = []
        self.closed_all = False

    def positions(self):
        return list(self._positions)

    def close_position(self, symbol):
        self.closed.append(symbol)

    def close_all_positions(self):
        self.closed_all = True


class FakeSettings:
    profile_name = "stocks"


class NullJournal:
    def log(self, *a, **k):
        pass


def _freeze_now(monkeypatch, when_et):
    """Pin engine's dt.datetime.now(ET) to a fixed ET time."""
    real_dt = dt.datetime

    class FrozenDateTime(real_dt):
        @classmethod
        def now(cls, tz=None):
            return when_et if tz else when_et.replace(tzinfo=None)

    monkeypatch.setattr(engine.dt, "datetime", FrozenDateTime)


# ── EOD flatten window ───────────────────────────────────────────────────────
def test_eod_flatten_fires_at_1550(monkeypatch):
    # Start of the close window — flatten while market orders can still fill.
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, 15, 50, tzinfo=ET))  # Wed
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is True


def test_eod_flatten_fires_at_1555(monkeypatch):
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, 15, 56, tzinfo=ET))  # Wed
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is True


def test_eod_flatten_does_NOT_fire_after_close(monkeypatch):
    # After 16:00 the market is closed: a SELL MARKET just cancels and the position
    # stays open, so re-firing every scan spammed dozens of Telegrams (the 2026-06-30
    # bug). The window must END at 16:00 so post-close scans are a no-op.
    for hh, mm in [(16, 0), (16, 5), (16, 30), (16, 50)]:
        _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, hh, mm, tzinfo=ET))
        b = FakeBroker([FakePos("AAPL")])
        engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
        assert b.closed_all is False, f"must NOT flatten at {hh}:{mm:02d} (market closed)"


def test_eod_flatten_skips_midday(monkeypatch):
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, 12, 0, tzinfo=ET))
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is False


def test_eod_flatten_skips_weekend(monkeypatch):
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 20, 15, 56, tzinfo=ET))  # Saturday
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is False


# ── stale-position backstop ──────────────────────────────────────────────────
def test_stale_backstop_closes_overnight(monkeypatch):
    today = dt.datetime(2026, 6, 17, 10, 0, tzinfo=ET)
    _freeze_now(monkeypatch, today)
    b = FakeBroker([FakePos("ARM")])
    # Pretend ARM was opened yesterday, not today.
    monkeypatch.setattr(engine, "_position_opened_today", lambda br, sym, d: False)
    engine.flatten_stale_positions(FakeSettings(), b, None, NullJournal())
    assert b.closed == ["ARM"]


def test_stale_backstop_keeps_today(monkeypatch):
    today = dt.datetime(2026, 6, 17, 10, 0, tzinfo=ET)
    _freeze_now(monkeypatch, today)
    b = FakeBroker([FakePos("ARM")])
    monkeypatch.setattr(engine, "_position_opened_today", lambda br, sym, d: True)
    engine.flatten_stale_positions(FakeSettings(), b, None, NullJournal())
    assert b.closed == []  # fresh position must NOT be churned
