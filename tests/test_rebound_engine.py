"""Tests for the live REBOUND engine — proves every safety control fires.

Uses fake Broker/data clients so nothing touches Alpaca. Covers: signal gating,
idempotency, circuit breaker, reconcile-when-holding, sizing, and EOD flatten.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tjrbot.live.rebound_engine import ReboundEngine, ReboundConfig, SYMBOL


# ---- fakes ----
class FakeAcct:
    def __init__(self, equity, last_equity):
        self.equity = str(equity); self.last_equity = str(last_equity)


class FakeBroker:
    def __init__(self, equity=100_000, last_equity=100_000, holding=False):
        self._eq = equity; self._last = last_equity; self._holding = holding
        self.submitted = []; self.closed = []; self.cancelled = []
        self._existing_orders = set()

    def account(self): return FakeAcct(self._eq, self._last)
    def equity(self): return float(self._eq)
    def has_position(self, sym): return self._holding
    def order_exists(self, coid): return coid in self._existing_orders
    def open_orders(self, sym=None): return []
    def submit_bracket(self, plan, client_order_id):
        self.submitted.append((plan, client_order_id))
        self._existing_orders.add(client_order_id)
    def cancel(self, oid): self.cancelled.append(oid)
    def close_position(self, sym): self.closed.append(sym)


class FakeQuote:
    def __init__(self, bid, ask): self.bid_price = bid; self.ask_price = ask


class FakeData:
    """Serves canned daily bars + a live quote."""
    def __init__(self, closes, price=500.0):
        self._closes = closes; self._price = price
    def get_stock_bars(self, req):
        n = len(self._closes)
        idx = pd.MultiIndex.from_tuples(
            [(SYMBOL, pd.Timestamp("2024-01-01") + pd.Timedelta(days=i)) for i in range(n)],
            names=["symbol", "timestamp"])
        df = pd.DataFrame({"open": self._closes, "high": [c + 1 for c in self._closes],
                           "low": [c - 1 for c in self._closes], "close": self._closes,
                           "volume": [1e6] * n}, index=idx)
        class R:
            def __init__(s, d): s.df = d
        return R(df)
    def get_stock_latest_quote(self, req):
        return {SYMBOL: FakeQuote(self._price - 0.05, self._price + 0.05)}


def _eng(broker, closes, price=500.0, cfg=None):
    return ReboundEngine(broker, FakeData(closes, price), cfg or ReboundConfig(), log=lambda *_: None)


# ---- signal gating ----
def test_enters_after_two_down_days():
    b = FakeBroker()
    # closes: ... up, down, down  -> the last row is "today's forming bar"; engine drops it,
    # so evaluate through the 2 down days
    eng = _eng(b, [500, 505, 503, 501, 500])   # last two (503->501->500) are down days
    res = eng.open_if_signal("2026-07-28")
    assert "entered" in res
    assert len(b.submitted) == 1


def test_no_entry_without_two_down_days():
    b = FakeBroker()
    eng = _eng(b, [500, 499, 498, 499, 500])   # last day up -> no signal
    res = eng.open_if_signal("2026-07-28")
    assert "no REBOUND signal" in res
    assert not b.submitted


# ---- idempotency ----
def test_idempotent_no_double_entry():
    b = FakeBroker()
    eng = _eng(b, [500, 505, 503, 501, 500])
    eng.open_if_signal("2026-07-28")
    res2 = eng.open_if_signal("2026-07-28")     # same day again
    assert "already placed" in res2
    assert len(b.submitted) == 1                # still only one


# ---- circuit breaker ----
def test_circuit_breaker_halts_on_big_daily_loss():
    b = FakeBroker(equity=96_000, last_equity=100_000)   # down 4% today
    eng = _eng(b, [500, 505, 503, 501, 500], cfg=ReboundConfig(daily_max_loss_pct=0.03))
    res = eng.open_if_signal("2026-07-28")
    assert "circuit breaker" in res
    assert not b.submitted


def test_circuit_breaker_allows_small_loss():
    b = FakeBroker(equity=99_000, last_equity=100_000)   # down 1% — under the 3% limit
    eng = _eng(b, [500, 505, 503, 501, 500])
    res = eng.open_if_signal("2026-07-28")
    assert "entered" in res


# ---- reconcile ----
def test_skips_when_already_holding():
    b = FakeBroker(holding=True)
    eng = _eng(b, [500, 505, 503, 501, 500])
    res = eng.open_if_signal("2026-07-28")
    assert "already holding" in res
    assert not b.submitted


# ---- sizing ----
def test_sizing_respects_risk_and_position_cap():
    b = FakeBroker(equity=100_000)
    eng = _eng(b, [500, 505, 503, 501, 500], price=500.0,
               cfg=ReboundConfig(risk_per_trade=0.01, stop_pct=0.02, max_position_pct=0.50))
    eng.open_if_signal("2026-07-28")
    plan, _ = b.submitted[0]
    # risk 1% of 100k = $1000; stop 2% of 500 = $10/share -> 100 shares
    # position cap 50% of 100k / 500 = 100 shares -> min(100,100)=100
    assert plan.qty == 100
    assert plan.side == "long" and plan.symbol == SYMBOL


# ---- EOD flatten ----
def test_flatten_closes_position():
    b = FakeBroker(holding=True)
    eng = _eng(b, [500, 505, 503, 501, 500])
    res = eng.flatten_for_exit()
    assert "flattened" in res
    assert b.closed == [SYMBOL]


def test_flatten_noop_when_flat():
    b = FakeBroker(holding=False)
    eng = _eng(b, [500, 505, 503, 501, 500])
    res = eng.flatten_for_exit()
    assert "no SPY position" in res
    assert not b.closed


# ---- isolation: engine must not IMPORT the paper strategies (only REBOUND) ----
def test_engine_isolated_from_paper_strategies():
    import ast
    import tjrbot.live.rebound_engine as m
    tree = ast.parse(open(m.__file__).read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for n in node.names:
                imported.add(f"{node.module}.{n.name}")
        elif isinstance(node, ast.Import):
            for n in node.names:
                imported.add(n.name)
    # the only strategy import allowed is REBOUND from futures_daily
    strat_imports = {i for i in imported if "strateg" in i.lower()}
    assert strat_imports == {"strategies.futures_daily.rebound"}, strat_imports
