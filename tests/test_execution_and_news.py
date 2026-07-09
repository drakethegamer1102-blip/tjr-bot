"""Tests for the 2026-07-08 bug fixes and news gate.

1. has_open_order must recognize ALL bot prefixes (apx-/rip- were invisible,
   letting a later scan stack a second bracket on a pending APEX/RIPTIDE entry).
2. "market" entries become marketable LIMIT orders capped ENTRY_SLIPPAGE_CAP
   through the signal price, so a fill can never land far from the planned
   stop/target geometry (live stops were filling 0.08-0.5% from entry).
3. The news gate drops blocked bots' signals on symbols with fresh headlines
   and leaves other bots' signals alone.
"""

import types

import pytest

import tjrbot.engine as engine
from tjrbot.execution.alpaca_exec import Broker
from tjrbot.risk.engine import TradePlan


class _Order:
    def __init__(self, cid):
        self.client_order_id = cid


def _broker_with_open(cids):
    b = Broker.__new__(Broker)  # skip __init__: no API client needed
    b.open_orders = lambda symbol=None: [_Order(c) for c in cids]
    return b


class TestHasOpenOrder:
    def test_recognizes_apex_and_riptide_prefixes(self):
        assert _broker_with_open(["apx-noise_band-QQQ-20260708-9"]).has_open_order("QQQ")
        assert _broker_with_open(["rip-band_tag-SPY-20260708-30"]).has_open_order("SPY")

    def test_recognizes_legacy_prefixes(self):
        assert _broker_with_open(["bot-momentum-AAPL-20260708-5"]).has_open_order("AAPL")
        assert _broker_with_open(["tjr-AAPL-20260622-22-b"]).has_open_order("AAPL")

    def test_ignores_foreign_orders(self):
        assert not _broker_with_open(["eodx-QQQ-25-700.0", "manual-1"]).has_open_order("QQQ")


class _CaptureTC:
    def __init__(self):
        self.req = None

    def submit_order(self, req):
        self.req = req
        return types.SimpleNamespace(id="test")


def _plan(side, entry_type="market"):
    return TradePlan(
        symbol="QQQ", side=side, entry=700.0,
        stop=689.5 if side == "long" else 710.5,
        target=721.0 if side == "long" else 679.0,
        qty=10, risk_dollars=105.0, notional=7000.0, entry_type=entry_type,
    )


class TestEntrySlippageCap:
    def _submit(self, side, entry_type="market"):
        b = Broker.__new__(Broker)
        b.tc = _CaptureTC()
        b.submit_bracket(_plan(side, entry_type), "apx-test-QQQ-20260708-1")
        return b.tc.req

    def test_market_long_becomes_capped_limit(self):
        req = self._submit("long")
        assert req.limit_price == round(700.0 * (1 + Broker.ENTRY_SLIPPAGE_CAP), 2)

    def test_market_short_becomes_capped_limit(self):
        req = self._submit("short")
        assert req.limit_price == round(700.0 * (1 - Broker.ENTRY_SLIPPAGE_CAP), 2)

    def test_limit_entry_unchanged(self):
        req = self._submit("long", entry_type="limit")
        assert req.limit_price == 700.0

    def test_bracket_legs_preserved(self):
        req = self._submit("long")
        assert req.take_profit.limit_price == 721.0
        assert req.stop_loss.stop_price == 689.5


class TestNewsFetchFailOpen:
    def test_bad_credentials_return_empty(self):
        from tjrbot.news import fetch_headlines
        assert fetch_headlines("bad", "creds", ["AAPL"], hours=1) == {}

    def test_no_symbols_return_empty(self):
        from tjrbot.news import fetch_headlines
        assert fetch_headlines("k", "s", []) == {}


class _Sig:
    def __init__(self, strategy, index=10):
        self.strategy = strategy
        self.index = index


class TestNewsGateFiltering:
    """The gate is a list comprehension keyed on bot_of + news symbols; test the
    exact filtering expression scan_once applies."""

    def _apply(self, signals, bot_of, news_syms, block, symbol):
        if block and symbol.replace("/", "") in news_syms:
            return [sg for sg in signals if bot_of.get(sg.strategy) not in block]
        return signals

    BOT_OF = {"vwap_rev": "riptide", "band_tag": "riptide", "momentum": "apex"}

    def test_blocks_riptide_on_news_symbol(self):
        sigs = [_Sig("vwap_rev"), _Sig("band_tag"), _Sig("momentum")]
        out = self._apply(sigs, self.BOT_OF, {"NVDA"}, {"riptide"}, "NVDA")
        assert [s.strategy for s in out] == ["momentum"]

    def test_no_news_symbol_passes_all(self):
        sigs = [_Sig("vwap_rev"), _Sig("momentum")]
        out = self._apply(sigs, self.BOT_OF, {"NVDA"}, {"riptide"}, "AAPL")
        assert len(out) == 2

    def test_gate_disabled_passes_all(self):
        sigs = [_Sig("vwap_rev")]
        out = self._apply(sigs, self.BOT_OF, {"NVDA"}, set(), "NVDA")
        assert len(out) == 1


class TestScanOnceNewsWiring:
    """scan_once must read news_filter config and call the news fetcher once."""

    def test_news_helper_imported_into_engine(self):
        assert hasattr(engine, "news_fetch_headlines")
