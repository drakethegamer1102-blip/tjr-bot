"""Position sizing, stop placement, and the daily kill-switch.

Your rule: a **10% stop** below entry and **3% account risk** per trade. Those two
numbers fully determine size:

    risk_dollars = risk_per_trade * equity          # 3% of account
    qty          = risk_dollars / (entry - stop)     # so a stop-out loses exactly 3%

With a 10% stop that means ~30% of the account goes into each position. The
notional is capped at `max_position_pct` so a tiny stop can never blow size up.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TradePlan:
    symbol: str
    side: str  # "long" | "short"
    entry: float
    stop: float
    target: float
    qty: float
    risk_dollars: float
    notional: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.03
    max_position_loss_pct: float | None = 0.10
    stop_mode: str = "fixed_pct"  # "fixed_pct" | "structural"
    min_rr: float = 2.0
    max_position_pct: float = 1.0  # never put more than this fraction of equity in one trade
    daily_max_losses: int = 3
    daily_max_loss_pct: float = 0.05
    max_trades_per_day: int = 3
    allow_fractional: bool = True

    @classmethod
    def from_settings(cls, s) -> "RiskConfig":
        st = s.strategy
        return cls(
            risk_per_trade=float(s.raw["risk_per_trade"]),
            max_position_loss_pct=s.raw.get("max_position_loss_pct"),
            stop_mode=s.raw.get("stop_mode", "fixed_pct"),
            min_rr=float(st.get("min_rr", 2.0)),
            daily_max_losses=int(s.raw.get("daily_max_losses", 3)),
            daily_max_loss_pct=float(s.raw.get("daily_max_loss_pct", 0.05)),
            max_trades_per_day=int(st.get("max_trades_per_day", 3)),
        )


def plan_trade(symbol: str, signal, equity: float, rc: RiskConfig) -> TradePlan | None:
    """Turn a raw signal into a sized, risk-checked trade plan (or None if invalid)."""
    side = signal.side
    entry = float(signal.entry)
    if entry <= 0:
        return None

    if rc.stop_mode == "fixed_pct" and rc.max_position_loss_pct:
        stop = (
            entry * (1 - rc.max_position_loss_pct)
            if side == "long"
            else entry * (1 + rc.max_position_loss_pct)
        )
    else:
        stop = float(signal.stop)
        # Honour your hard cap: never risk more than max_position_loss_pct of entry,
        # even if the structural level is wider than that.
        if rc.max_position_loss_pct:
            if side == "long":
                stop = max(stop, entry * (1 - rc.max_position_loss_pct))
            else:
                stop = min(stop, entry * (1 + rc.max_position_loss_pct))

    per_unit_risk = abs(entry - stop)
    if per_unit_risk <= 0:
        return None

    qty = (rc.risk_per_trade * equity) / per_unit_risk
    max_notional = rc.max_position_pct * equity
    if qty * entry > max_notional:
        qty = max_notional / entry
    if not rc.allow_fractional:
        qty = float(int(qty))
    if qty <= 0:
        return None

    target = (
        entry + rc.min_rr * per_unit_risk
        if side == "long"
        else entry - rc.min_rr * per_unit_risk
    )
    return TradePlan(
        symbol=symbol,
        side=side,
        entry=entry,
        stop=float(stop),
        target=float(target),
        qty=qty,
        risk_dollars=qty * per_unit_risk,
        notional=qty * entry,
        reasons=list(getattr(signal, "reasons", [])),
    )


@dataclass
class DailyRiskState:
    """Tracks today's realised results so the kill-switch can halt trading."""

    starting_equity: float
    realized_pnl: float = 0.0
    losses: int = 0
    trades: int = 0

    def record(self, pnl: float) -> None:
        self.realized_pnl += pnl
        self.trades += 1
        if pnl < 0:
            self.losses += 1

    def halted(self, rc: RiskConfig) -> str | None:
        """Return a reason string if trading should stop for the day, else None."""
        if self.trades >= rc.max_trades_per_day:
            return "max trades per day reached"
        if self.losses >= rc.daily_max_losses:
            return "max losses per day reached"
        if self.realized_pnl <= -rc.daily_max_loss_pct * self.starting_equity:
            return "daily loss limit reached"
        return None
