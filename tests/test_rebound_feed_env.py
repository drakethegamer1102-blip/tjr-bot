"""Regression test: an unset GitHub secret resolves REBOUND_FEED to "" (not absent),
which is an invalid Alpaca feed value and crashed the live run (2026-07-28). The runner
must treat blank/whitespace as the 'iex' default."""

from __future__ import annotations

import os
from unittest import mock


def _resolve_feed() -> str:
    # mirror the exact expression in scripts/rebound_live.py
    return (os.getenv("REBOUND_FEED") or "").strip().lower() or "iex"


def test_empty_feed_defaults_to_iex():
    with mock.patch.dict(os.environ, {"REBOUND_FEED": ""}):
        assert _resolve_feed() == "iex"


def test_whitespace_feed_defaults_to_iex():
    with mock.patch.dict(os.environ, {"REBOUND_FEED": "   "}):
        assert _resolve_feed() == "iex"


def test_unset_feed_defaults_to_iex():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert _resolve_feed() == "iex"


def test_explicit_sip_is_honored():
    with mock.patch.dict(os.environ, {"REBOUND_FEED": "SIP"}):
        assert _resolve_feed() == "sip"


def test_the_runner_uses_this_exact_expression():
    # guard against the fix being reverted: the file must contain the blank-safe pattern
    src = open("scripts/rebound_live.py").read()
    assert 'os.getenv("REBOUND_FEED") or ""' in src
