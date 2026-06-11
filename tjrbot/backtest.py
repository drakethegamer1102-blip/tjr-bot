"""Event-driven backtest of the TJR strategy on intraday bars.

Causal by construction:
  * Sweep levels = the PRIOR day's high/low (known at today's open).
  * Daily bias  = higher-timeframe structure built only from bars before today.
  * Entry       = a limit fill when price retraces into the signal's FVG.
  * Exit        = whichever comes first: stop, target, or end-of-day flat
                  (day trading -> never hold overnight).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .risk.engine import DailyRiskState, RiskConfig, plan_trade
from .smc.session import ET, in_session
from .strategy import find_trades


@dataclass
class Trade:
    symbol: str
    side: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry: float
    exit: float
    stop: float
    target: float
    qty: float
    pnl: float
    outcome: str  # "target" | "stop" | "eod"


@dataclass
class BacktestResult:
    symbol: str
    timeframe: str
    start_equity: float
    end_equity: float
    trades: list[Trade] = field(default_factory=list)


def run_backtest(
    bars: pd.DataFrame,
    symbol: str,
    rc: RiskConfig,
    *,
    timeframe: str = "5Min",
    sessions: tuple[str, ...] = ("ny_open",),
    entry_valid_bars: int = 12,
    start_equity: float = 100_000.0,
    strat: dict | None = None,
) -> BacktestResult:
    strat = strat or {}
    bars = bars.sort_index()
    if bars.index.tz is None:
        bars.index = bars.index.tz_localize("UTC")

    day_key = bars.index.tz_convert(ET).normalize()
    groups = list(bars.groupby(day_key))

    equity = start_equity
    result = BacktestResult(symbol, timeframe, start_equity, start_equity)

    for i in range(1, len(groups)):
        prev = groups[i - 1][1]
        today = groups[i][1]
        if len(today) < 10:
            continue

        pdh, pdl = float(prev["high"].max()), float(prev["low"].min())

        hist = bars[bars.index < today.index[0]]
        htf = (
            hist.resample("1h")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
        )

        signals = find_trades(
            today,
            levels=[pdh, pdl],
            htf_bars=htf if len(htf) >= 5 else None,
            pivot_strength=int(strat.get("pivot_strength", 2)),
            fvg_atr_mult=float(strat.get("fvg_atr_mult", 0.25)),
            atr_period=int(strat.get("atr_period", 14)),
            confirm_window=int(strat.get("confirm_window", 10)),
            min_rr=rc.min_rr,
            sessions=list(sessions),
            use_bias=True,
        )

        state = DailyRiskState(starting_equity=equity)
        highs = today["high"].to_numpy()
        lows = today["low"].to_numpy()
        closes = today["close"].to_numpy()
        times = today.index
        n = len(today)
        last_exit = -1

        for s in sorted(signals, key=lambda x: x.index):
            if state.halted(rc):
                break
            if s.index <= last_exit:  # no overlapping positions
                continue
            plan = plan_trade(symbol, s, equity, rc)
            if plan is None:
                continue

            # --- limit fill on the retrace into the FVG ---
            fill = None
            for j in range(s.index + 1, min(s.index + 1 + entry_valid_bars, n)):
                if s.side == "long" and lows[j] <= plan.entry:
                    fill = j
                    break
                if s.side == "short" and highs[j] >= plan.entry:
                    fill = j
                    break
            if fill is None:
                continue

            # --- walk forward to the exit ---
            ex_idx, ex_price, outcome = None, None, None
            for k in range(fill + 1, n):
                if s.side == "long":
                    if lows[k] <= plan.stop:  # stop checked first (conservative)
                        ex_idx, ex_price, outcome = k, plan.stop, "stop"
                        break
                    if highs[k] >= plan.target:
                        ex_idx, ex_price, outcome = k, plan.target, "target"
                        break
                else:
                    if highs[k] >= plan.stop:
                        ex_idx, ex_price, outcome = k, plan.stop, "stop"
                        break
                    if lows[k] <= plan.target:
                        ex_idx, ex_price, outcome = k, plan.target, "target"
                        break
            if ex_idx is None:  # end-of-day flat
                ex_idx, ex_price, outcome = n - 1, float(closes[n - 1]), "eod"

            pnl = (
                plan.qty * (ex_price - plan.entry)
                if s.side == "long"
                else plan.qty * (plan.entry - ex_price)
            )
            equity += pnl
            state.record(pnl)
            last_exit = ex_idx
            result.trades.append(
                Trade(
                    symbol, s.side, times[fill], times[ex_idx],
                    plan.entry, float(ex_price), plan.stop, plan.target,
                    plan.qty, float(pnl), outcome,
                )
            )

    result.end_equity = equity
    return result


def summarize(res: BacktestResult) -> dict:
    t = res.trades
    n = len(t)
    wins = [x for x in t if x.pnl > 0]
    losses = [x for x in t if x.pnl < 0]
    gross_win = sum(x.pnl for x in wins)
    gross_loss = -sum(x.pnl for x in losses)

    eq, peak, mdd = res.start_equity, res.start_equity, 0.0
    for x in t:
        eq += x.pnl
        peak = max(peak, eq)
        if peak > 0:
            mdd = max(mdd, (peak - eq) / peak)

    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / n) if n else 0.0,
        "target_hits": sum(1 for x in t if x.outcome == "target"),
        "stop_hits": sum(1 for x in t if x.outcome == "stop"),
        "eod_exits": sum(1 for x in t if x.outcome == "eod"),
        "avg_win": (gross_win / len(wins)) if wins else 0.0,
        "avg_loss": (gross_loss / len(losses)) if losses else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0,
        "expectancy": (sum(x.pnl for x in t) / n) if n else 0.0,
        "total_return": (res.end_equity / res.start_equity - 1) if res.start_equity else 0.0,
        "end_equity": res.end_equity,
        "max_drawdown": mdd,
    }


def backtest_strategy(
    bars: pd.DataFrame,
    symbol: str,
    build_signals,
    rc: RiskConfig,
    *,
    sessions: tuple[str, ...] = ("ny_open", "ny_pm"),
    entry_valid_bars: int = 12,
    start_equity: float = 100_000.0,
) -> BacktestResult:
    """Strategy-agnostic backtest. `build_signals(today, prev, hist)` returns Signals.

    Honors each signal's `entry_type`: "limit" fills on a retrace to entry; "market"
    fills at the signal bar's close. Exits: stop / target / end-of-day flat.
    """
    bars = bars.sort_index()
    if bars.index.tz is None:
        bars.index = bars.index.tz_localize("UTC")
    day_key = bars.index.tz_convert(ET).normalize()
    groups = list(bars.groupby(day_key))

    equity = start_equity
    result = BacktestResult(symbol, "", start_equity, start_equity)

    for i in range(1, len(groups)):
        prev, today = groups[i - 1][1], groups[i][1]
        if len(today) < 12:
            continue
        hist = bars[bars.index < today.index[0]]
        try:
            signals = build_signals(today, prev, hist) or []
        except Exception:  # noqa: BLE001
            continue
        signals = [s for s in signals if in_session(today.index[s.index], list(sessions))]
        if not signals:
            continue

        highs, lows = today["high"].to_numpy(), today["low"].to_numpy()
        closes, times, n = today["close"].to_numpy(), today.index, len(today)
        state = DailyRiskState(starting_equity=equity)
        last_exit = -1

        for s in sorted(signals, key=lambda x: x.index):
            if state.halted(rc):
                break
            if s.index <= last_exit:
                continue
            plan = plan_trade(symbol, s, equity, rc)
            if plan is None:
                continue

            if s.entry_type == "market":
                fill = s.index
            else:
                fill = None
                for j in range(s.index + 1, min(s.index + 1 + entry_valid_bars, n)):
                    if (s.side == "long" and lows[j] <= plan.entry) or (
                        s.side == "short" and highs[j] >= plan.entry
                    ):
                        fill = j
                        break
                if fill is None:
                    continue

            ex_idx = ex_price = outcome = None
            for k in range(fill + 1, n):
                if s.side == "long":
                    if lows[k] <= plan.stop:
                        ex_idx, ex_price, outcome = k, plan.stop, "stop"
                        break
                    if highs[k] >= plan.target:
                        ex_idx, ex_price, outcome = k, plan.target, "target"
                        break
                else:
                    if highs[k] >= plan.stop:
                        ex_idx, ex_price, outcome = k, plan.stop, "stop"
                        break
                    if lows[k] <= plan.target:
                        ex_idx, ex_price, outcome = k, plan.target, "target"
                        break
            if ex_idx is None:
                ex_idx, ex_price, outcome = n - 1, float(closes[n - 1]), "eod"

            pnl = (
                plan.qty * (ex_price - plan.entry)
                if s.side == "long"
                else plan.qty * (plan.entry - ex_price)
            )
            equity += pnl
            state.record(pnl)
            last_exit = ex_idx
            result.trades.append(
                Trade(symbol, s.side, times[fill], times[ex_idx], plan.entry, float(ex_price),
                      plan.stop, plan.target, plan.qty, float(pnl), outcome)
            )

    result.end_equity = equity
    return result
