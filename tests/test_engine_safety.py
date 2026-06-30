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
    def __init__(self, positions, opened_today=None, pending_ah=False):
        self._positions = positions
        self._opened_today = opened_today or {}
        self._pending_ah = pending_ah
        self.closed = []
        self.closed_all = False          # regular-hours close_all_positions called
        self.closed_all_ah = False       # after-hours close called

    def positions(self):
        return list(self._positions)

    def close_position(self, symbol):
        self.closed.append(symbol)

    def close_all_positions(self):
        self.closed_all = True

    def close_all_positions_extended_hours(self, slippage_pct=0.01):
        self.closed_all_ah = True
        return len(self._positions)

    def open_orders(self, symbol=None):
        class _O:
            def __init__(s, cid): s.client_order_id = cid
        return [_O("eodx-QQQ-25-700.0")] if self._pending_ah else []


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
def test_eod_flatten_regular_close_at_1545(monkeypatch):
    # 15:45-15:59: market still open -> plain market close (fills immediately).
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, 15, 45, tzinfo=ET))  # Wed
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is True and b.closed_all_ah is False


def test_eod_flatten_regular_close_at_1556(monkeypatch):
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, 15, 56, tzinfo=ET))
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is True and b.closed_all_ah is False


def test_eod_flatten_afterhours_close_post_1600(monkeypatch):
    # 16:00-19:45: market closed -> extended-hours close (NOT a plain market order,
    # which would just cancel). This is what actually exits the position.
    for hh, mm in [(16, 0), (16, 30), (18, 0), (19, 30)]:
        _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, hh, mm, tzinfo=ET))
        b = FakeBroker([FakePos("AAPL")])
        engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
        assert b.closed_all_ah is True, f"after-hours close must fire at {hh}:{mm:02d}"
        assert b.closed_all is False  # never a doomed regular market order post-close


def test_eod_flatten_afterhours_skips_if_pending(monkeypatch):
    # An eodx- exit already pending -> do NOT submit another (no churn, no re-notify).
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, 16, 30, tzinfo=ET))
    b = FakeBroker([FakePos("AAPL")], pending_ah=True)
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all_ah is False


def test_eod_flatten_noop_after_ah_cutoff(monkeypatch):
    # After 19:45 we stop trying (too late to queue) -> no churn overnight.
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, 20, 0, tzinfo=ET))
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is False and b.closed_all_ah is False


def test_eod_flatten_skips_midday(monkeypatch):
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 17, 12, 0, tzinfo=ET))
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is False and b.closed_all_ah is False


def test_eod_flatten_skips_weekend(monkeypatch):
    _freeze_now(monkeypatch, dt.datetime(2026, 6, 20, 15, 56, tzinfo=ET))  # Saturday
    b = FakeBroker([FakePos("AAPL")])
    engine.flatten_if_eod(FakeSettings(), b, None, NullJournal())
    assert b.closed_all is False and b.closed_all_ah is False


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
