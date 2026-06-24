"""Tests for position sizing, stop placement, and the daily kill-switch."""

from tjrbot.risk.engine import DailyRiskState, RiskConfig, plan_trade
from tjrbot.smc.signals import Signal


def sig(side="long", entry=100.0, stop=90.0, target=120.0):
    return Signal(index=0, side=side, entry=entry, stop=stop, target=target, reasons=[])


def test_fixed_pct_sizing():
    # 10% stop + 3% risk on $100k -> risk $3000, $10/share risk -> 300 shares (=$30k, 30%)
    rc = RiskConfig(risk_per_trade=0.03, max_position_loss_pct=0.10, stop_mode="fixed_pct")
    plan = plan_trade("AAPL", sig(), equity=100_000, rc=rc)
    assert plan is not None
    assert abs(plan.stop - 90.0) < 1e-9
    assert abs(plan.qty - 300.0) < 1e-9
    assert abs(plan.notional - 30_000.0) < 1e-9
    assert abs(plan.risk_dollars - 3_000.0) < 1e-9
    assert abs(plan.target - 120.0) < 1e-9  # entry + 2R


def test_short_sizing():
    rc = RiskConfig(risk_per_trade=0.03, max_position_loss_pct=0.10, stop_mode="fixed_pct")
    plan = plan_trade("AAPL", sig(side="short"), equity=100_000, rc=rc)
    assert plan.side == "short"
    assert abs(plan.stop - 110.0) < 1e-9  # 10% above entry
    assert abs(plan.target - 80.0) < 1e-9  # entry - 2R


def test_notional_cap():
    rc = RiskConfig(
        risk_per_trade=0.03, max_position_loss_pct=0.10, stop_mode="fixed_pct", max_position_pct=0.20
    )
    plan = plan_trade("AAPL", sig(), equity=100_000, rc=rc)
    assert abs(plan.notional - 20_000.0) < 1e-9  # capped at 20%
    assert abs(plan.qty - 200.0) < 1e-9


def test_structural_stop_mode():
    rc = RiskConfig(risk_per_trade=0.03, stop_mode="structural", max_position_pct=1.0)
    plan = plan_trade("AAPL", sig(entry=100, stop=98), equity=100_000, rc=rc)
    # $2/share risk, $3000 risk -> 1500 shares = $150k notional, capped to $100k -> 1000 shares
    assert abs(plan.notional - 100_000.0) < 1e-9
    assert abs(plan.qty - 1000.0) < 1e-9


def test_min_stop_floor_widens_tight_long_stop():
    # A structural stop only 0.2% away must be widened to the 0.5% floor (the live
    # "stopped by pennies" bug). Target keeps the same 3R multiple off the wider risk.
    rc = RiskConfig(risk_per_trade=0.03, stop_mode="structural", max_position_loss_pct=0.10,
                    min_rr=3.0, min_stop_pct=0.005, max_position_pct=1.0)
    plan = plan_trade("AAPL", sig(entry=100.0, stop=99.8, target=103.0), equity=100_000, rc=rc)
    assert abs(plan.stop - 99.5) < 1e-9          # widened to 0.5% below entry
    assert abs(plan.target - 101.5) < 1e-9       # entry + 3 * 0.5 (R:R preserved)


def test_min_stop_floor_widens_tight_short_stop():
    rc = RiskConfig(risk_per_trade=0.03, stop_mode="structural", max_position_loss_pct=0.10,
                    min_rr=3.0, min_stop_pct=0.005, max_position_pct=1.0)
    plan = plan_trade("AAPL", sig(side="short", entry=100.0, stop=100.2, target=97.0),
                      equity=100_000, rc=rc)
    assert abs(plan.stop - 100.5) < 1e-9         # widened to 0.5% above entry
    assert abs(plan.target - 98.5) < 1e-9        # entry - 3 * 0.5


def test_min_stop_floor_leaves_wide_stop_untouched():
    # A stop already wider than the floor is unchanged.
    rc = RiskConfig(risk_per_trade=0.03, stop_mode="structural", max_position_loss_pct=0.10,
                    min_rr=3.0, min_stop_pct=0.005, max_position_pct=1.0)
    plan = plan_trade("AAPL", sig(entry=100.0, stop=97.0, target=109.0), equity=100_000, rc=rc)
    assert abs(plan.stop - 97.0) < 1e-9          # 3% gap > 0.5% floor -> untouched


def test_kill_switch_losses():
    rc = RiskConfig(daily_max_losses=3, daily_max_loss_pct=0.99, max_trades_per_day=99)
    st = DailyRiskState(starting_equity=100_000)
    assert st.halted(rc) is None
    st.record(-100)
    st.record(-100)
    st.record(-100)
    assert st.halted(rc) == "max losses per day reached"


def test_kill_switch_daily_loss():
    rc = RiskConfig(daily_max_losses=99, daily_max_loss_pct=0.05, max_trades_per_day=99)
    st = DailyRiskState(starting_equity=100_000)
    st.record(-3000)
    assert st.halted(rc) is None
    st.record(-3000)  # total -6000 > 5% of 100k
    assert st.halted(rc) == "daily loss limit reached"


def test_daily_loss_exceeded():
    from tjrbot.risk.engine import daily_loss_exceeded

    assert daily_loss_exceeded(94000, 100000, 0.05) is True    # -6% breaches -5%
    assert daily_loss_exceeded(96000, 100000, 0.05) is False   # -4% is fine
    assert daily_loss_exceeded(110000, 100000, 0.05) is False  # up day
    assert daily_loss_exceeded(90000, 0, 0.05) is False        # no baseline -> never halts
