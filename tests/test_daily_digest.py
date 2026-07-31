"""Tests for the per-strategy daily digest formatter (separate-message win/loss breakdown)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "daily_strategy_digest",
    Path(__file__).resolve().parent.parent / "scripts" / "daily_strategy_digest.py")
digest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(digest)


def test_verdict_labels():
    assert "WIN" in digest._verdict(100)
    assert "LOSS" in digest._verdict(-100)
    assert "flat" in digest._verdict(0)


def test_day_groups_by_strategy_with_net():
    rows = [{"strat": "orb", "pnl": 500}, {"strat": "orb", "pnl": -100},
            {"strat": "band_tag", "pnl": 50}]
    body = digest._fmt_day(rows, "HEAD", "none")
    assert "HEAD" in body
    assert "orb" in body and "2t" in body           # orb aggregated: 2 trades
    assert "band_tag" in body and "1t" in body
    assert "$+400" in body or "$+450" in body        # orb net +400; band_tag +50
    assert "day net" in body and "$+450" in body     # total across strategies


def test_empty_day_sends_note():
    body = digest._fmt_day([], "HEAD", "no trades today.")
    assert "no trades today." in body
    assert "day net" not in body                     # nothing to net


def test_losing_day_flagged_loss():
    rows = [{"strat": "orb", "pnl": -1469}]
    body = digest._fmt_day(rows, "HEAD", "none")
    assert "LOSS" in body and "$-1,469" in body


def test_expanded_trade_line_shows_detail():
    rows = [{"strat": "orb", "pnl": 72, "sym": "GOOGL", "side": "short",
             "entry": 333.24, "exit": 331.87, "qty": 53}]
    body = digest._fmt_day(rows, "HEAD", "none")
    assert "GOOGL SHORT" in body
    assert "333.24" in body and "331.87" in body     # entry->exit shown
    assert "×53" in body                              # qty shown
    assert "$+72" in body and "WIN" in body


def test_ledger_trade_line_shows_reason():
    t = {"strat": "DIPBUYER", "pnl": 1345, "sym": "MES", "side": "long",
         "entry": 7338, "exit": 7472.5, "note": "10d-low pullback"}
    body = digest._fmt_day([t], "HEAD", "none")
    assert "10d-low pullback" in body                 # the strategy's reason is included
    assert "MES LONG" in body
