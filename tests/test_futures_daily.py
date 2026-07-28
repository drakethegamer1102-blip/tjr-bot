"""Tests for the three validated daily futures strategies (DAYBREAK/REBOUND/TIDERIDER)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tjrbot.strategies import futures_daily as fd


def _daily(closes, opens=None, highs=None, lows=None):
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    opens = opens or closes
    return pd.DataFrame({
        "open": opens, "high": highs or [c + 1 for c in closes],
        "low": lows or [c - 1 for c in closes], "close": closes,
    }, index=idx)


def test_daybreak_fires_in_bull_regime():
    # 210 rising closes -> last close well above the 200d SMA
    closes = list(np.linspace(4000, 5000, 210))
    plan = fd.daybreak(_daily(closes))
    assert plan and plan["name"] == "DAYBREAK" and plan["side"] == "long"


def test_daybreak_silent_below_sma():
    # rising then a hard drop below the 200d average
    closes = list(np.linspace(5000, 5200, 205)) + [3000, 2900, 2800, 2700, 2600]
    assert fd.daybreak(_daily(closes)) is None


def test_daybreak_needs_history():
    assert fd.daybreak(_daily(list(range(50)))) is None


def test_rebound_fires_after_two_down_days():
    closes = [100, 101, 102, 101, 100]      # last two are down days
    plan = fd.rebound(_daily(closes))
    assert plan and plan["name"] == "REBOUND" and plan["side"] == "long"


def test_rebound_silent_without_two_down():
    closes = [100, 99, 98, 99, 100]         # last day is UP
    assert fd.rebound(_daily(closes)) is None


def test_gapfill_emits_plan_with_gap_requirement():
    # GAPFILL always emits a plan carrying the gap requirement + prior close; the runner
    # confirms the actual gap at the open.
    closes = [100, 101, 102, 103, 104]
    plan = fd.gapfill(_daily(closes))
    assert plan and plan["name"] == "GAPFILL" and plan["side"] == "long"
    assert plan["requires_gap_down_pct"] > 0
    assert plan["prev_close"] == 104


def test_gapfill_needs_two_bars():
    assert fd.gapfill(_daily([100])) is None


def test_registry_has_all_three_and_is_isolated():
    assert set(fd.REGISTRY) == {"DAYBREAK", "REBOUND", "GAPFILL"}
    # these must not collide with the existing intraday strategies
    from tjrbot.strategies import REGISTRY as INTRADAY
    assert not (set(fd.REGISTRY) & set(INTRADAY))
