"""Tests for the APEX/RIPTIDE virtual-bot layer and the three new strategies."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tjrbot.config import load_settings
from tjrbot.engine import BOT_PREFIXES, _bot_of_map
from tjrbot.risk.engine import RiskConfig, plan_trade
from tjrbot.smc.signals import Signal
from tjrbot.strategies import NEEDS_HIST, REGISTRY, band_tag, gap_fade, noise_band


def _bars(closes, start="2026-07-06 09:30", freq="5min", spread=0.2, vol=1_000_000):
    idx = pd.date_range(start=start, periods=len(closes), freq=freq, tz="America/New_York").tz_convert("UTC")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "open": c, "high": c + spread, "low": c - spread, "close": c,
        "volume": [vol] * len(c),
    }, index=idx)


def _hist_days(n_days=15, base=100.0, drift=0.0, bars_per_day=78):
    """n_days of flat-ish 5-min sessions ending the day before the test session."""
    frames = []
    day = pd.Timestamp("2026-06-12 09:30", tz="America/New_York")
    for d in range(n_days):
        base_d = base + drift * d
        closes = base_d + np.sin(np.linspace(0, 4, bars_per_day))  # ±1 wiggle
        frames.append(_bars(closes, start=day.strftime("%Y-%m-%d %H:%M")))
        day += pd.tseries.offsets.BDay(1)
    return pd.concat(frames)


# ── registry / wiring ─────────────────────────────────────────────────────────

def test_new_strategies_registered():
    for name in ("noise_band", "gap_fade", "band_tag"):
        assert name in REGISTRY
        assert name in NEEDS_HIST


def test_bot_prefixes_cover_new_bots():
    assert "apx-" in BOT_PREFIXES and "rip-" in BOT_PREFIXES


def test_config_bot_assignments():
    s = load_settings()
    bot_of = _bot_of_map(s)
    assert bot_of.get("momentum") == "apex"
    assert bot_of.get("noise_band") == "apex"
    assert bot_of.get("vwap_rev") == "riptide"
    assert bot_of.get("gap_fade") == "riptide"
    assert bot_of.get("band_tag") == "riptide"
    assert "tjr" not in bot_of  # legacy stays legacy (and disabled)
    bots = s.raw["bots"]
    # Envelope sanity: learning phase = tighter per-trade risk than the legacy 3%.
    for b in bots.values():
        assert float(b["risk_per_trade"]) <= 0.01
        assert float(b["daily_max_loss_pct"]) <= 0.025


# ── per-bot risk overrides ────────────────────────────────────────────────────

def test_with_bot_overrides_never_raises_risk():
    rc = RiskConfig(risk_per_trade=0.03)
    out = rc.with_bot_overrides({"risk_per_trade": 0.10, "honor_signal_target": True})
    assert out.risk_per_trade == 0.03  # min() guard: cannot raise above base
    out2 = rc.with_bot_overrides({"risk_per_trade": 0.01})
    assert out2.risk_per_trade == 0.01


def test_plan_trade_honors_signal_target():
    sig = Signal(index=1, side="long", entry=100.0, stop=99.0, target=100.8)
    rc = RiskConfig(risk_per_trade=0.01, stop_mode="structural", min_rr=3.0,
                    min_stop_pct=0.004, honor_signal_target=True,
                    max_position_loss_pct=0.10)
    plan = plan_trade("SPY", sig, 100_000, rc)
    assert plan is not None
    assert plan.target == pytest.approx(100.8)  # NOT rewritten to 3R (=103)


def test_plan_trade_legacy_still_rewrites_target():
    sig = Signal(index=1, side="long", entry=100.0, stop=99.0, target=100.8)
    rc = RiskConfig(risk_per_trade=0.01, stop_mode="structural", min_rr=3.0,
                    min_stop_pct=0.004, honor_signal_target=False,
                    max_position_loss_pct=0.10)
    plan = plan_trade("SPY", sig, 100_000, rc)
    risk = plan.entry - plan.stop
    assert plan.target == pytest.approx(plan.entry + 3.0 * risk)


# ── new strategies ────────────────────────────────────────────────────────────

def test_noise_band_long_on_upside_break():
    hist = _hist_days()
    # Today: open 100, grinds up to 104 — way beyond the ~1% historical envelope.
    closes = np.linspace(100, 104, 60)
    today = _bars(closes, start="2026-07-06 09:30")
    sigs = noise_band.generate(today, hist=hist)
    assert sigs, "expected a long noise-band signal on a strong trend day"
    assert sigs[0].side == "long"
    assert sigs[0].strategy == "noise_band"
    assert sigs[0].stop < sigs[0].entry < sigs[0].target


def test_noise_band_quiet_day_no_signal():
    hist = _hist_days()
    closes = 100 + 0.05 * np.sin(np.linspace(0, 6, 60))  # dead-flat day
    today = _bars(closes, start="2026-07-06 09:30")
    assert noise_band.generate(today, hist=hist) == []


def test_gap_fade_shorts_small_gap_up():
    hist = _hist_days()
    prev_close = float(hist["close"].iloc[-1])
    gap_open = prev_close * 1.002  # +0.2% gap: inside the fade window
    closes = np.full(12, gap_open)
    today = _bars(closes, start="2026-07-06 09:30")
    sigs = gap_fade.generate(today, hist=hist)
    assert sigs and sigs[0].side == "short"
    assert sigs[0].target == pytest.approx(prev_close)


def test_gap_fade_skips_large_gap():
    hist = _hist_days()
    prev_close = float(hist["close"].iloc[-1])
    closes = np.full(12, prev_close * 1.02)  # +2% gap: news-driven, skip
    today = _bars(closes, start="2026-07-06 09:30")
    assert gap_fade.generate(today, hist=hist) == []


def test_band_tag_long_needs_uptrend_gate():
    hist_up = _hist_days(drift=0.5)     # rising daily closes -> longs allowed
    hist_dn = _hist_days(drift=-0.5)    # falling -> longs blocked
    # Flat mid-day then a sharp 3-bar plunge: tags the lower Keltner band, RSI(2) ~ 0.
    closes = np.concatenate([np.full(40, 100.0), [99.2, 98.4, 97.6]])
    today = _bars(closes, start="2026-07-06 09:30")
    sigs_up = band_tag.generate(today, hist=hist_up)
    assert sigs_up and sigs_up[0].side == "long"
    assert sigs_up[0].target > sigs_up[0].entry  # target = band midline above
    sigs_dn = band_tag.generate(today, hist=hist_dn)
    assert all(s.side != "long" for s in sigs_dn)
