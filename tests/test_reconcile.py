"""Tests for trade reconciliation (closed bracket orders -> recorded win/loss)."""

from tjrbot.journal import Journal
from tjrbot.reconcile import compute_pnl, reconcile


class _Leg:
    def __init__(self, status, filled_avg_price, filled_at="2026-01-02T15:00:00Z"):
        self.status = status
        self.filled_avg_price = filled_avg_price
        self.filled_at = filled_at


class _Order:
    def __init__(self, coid, symbol, side, status, entry, qty, legs):
        self.client_order_id = coid
        self.symbol = symbol
        self.side = side
        self.status = status
        self.filled_avg_price = entry
        self.filled_qty = qty
        self.legs = legs
        self.filled_at = "2026-01-02T14:30:00Z"


class _Broker:
    def __init__(self, orders):
        self._orders = orders

    def closed_orders(self, limit=200):
        return self._orders


def test_compute_pnl():
    assert compute_pnl("long", 100, 110, 10) == 100
    assert compute_pnl("short", 100, 90, 10) == 100
    assert compute_pnl("long", 100, 95, 10) == -50


def test_reconcile_records_win_and_is_idempotent(tmp_path):
    j = Journal(tmp_path / "j.db")
    # long entry 100, take-profit leg filled at 110, qty 10 -> +100
    o = _Order(
        "bot-tjr-AAPL-20260102-5", "AAPL", "OrderSide.BUY", "OrderStatus.FILLED", 100.0, 10,
        [_Leg("OrderStatus.FILLED", 110.0), _Leg("OrderStatus.CANCELED", None)],
    )
    assert reconcile(_Broker([o]), j) == 1
    trades = j.trades()
    assert len(trades) == 1
    assert abs(trades[0]["pnl"] - 100.0) < 1e-9
    assert trades[0]["outcome"] == "target"
    # running again must not double-record
    assert reconcile(_Broker([o]), j) == 0


def test_reconcile_skips_open_positions(tmp_path):
    j = Journal(tmp_path / "j.db")
    # entry filled but neither exit leg filled -> still open, do not record
    o = _Order(
        "bot-tjr-MSFT-20260102-3", "MSFT", "OrderSide.BUY", "OrderStatus.FILLED", 200.0, 5,
        [_Leg("OrderStatus.NEW", None), _Leg("OrderStatus.NEW", None)],
    )
    assert reconcile(_Broker([o]), j) == 0
    assert len(j.trades()) == 0
