"""Live paper-trading engine: scan symbols -> size -> place bracket orders -> alert.

Designed to run unattended on an always-on host. Each scan:
  1. Skips unless we're inside the trading session (unless `force`).
  2. For each watchlist symbol with no open position, pulls recent bars.
  3. Builds prior-day liquidity levels + higher-timeframe bias.
  4. Finds a TJR signal that completed on the most recent closed bar.
  5. Sizes it with the risk engine, submits a bracket order, alerts Telegram,
     and journals it. Idempotent: a given setup is ordered at most once.
"""

from __future__ import annotations

import datetime as dt
import time

import pandas as pd

from .config import Settings
from .data.alpaca_data import get_crypto_bars, get_stock_bars
from .journal import Journal
from .risk.engine import RiskConfig, plan_trade
from .reconcile import reconcile
from .smc.session import ET, in_session
from .strategy import find_trades

_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _recent_bars(s: Settings, symbol: str, tf: str, days: int = 3) -> pd.DataFrame:
    if "/" in symbol:
        return get_crypto_bars(s.alpaca_key, s.alpaca_secret, symbol, tf, days)
    return get_stock_bars(s.alpaca_key, s.alpaca_secret, symbol, tf, days)


def _sessions_for(s: Settings) -> tuple[str, ...]:
    return ("ny", "london") if s.profile_name == "crypto" else ("ny_open",)


def _format_alert(plan, status: str) -> str:
    arrow = "🟢 LONG" if plan.side == "long" else "🔴 SHORT"
    return (
        f"{arrow} <b>{plan.symbol}</b>  ({status})\n"
        f"Entry ${plan.entry:.2f} | Stop ${plan.stop:.2f} | Target ${plan.target:.2f}\n"
        f"Qty {plan.qty:g}  (~${plan.notional:,.0f})\n"
        f"Why: {', '.join(plan.reasons)}"
    )


def flatten_if_eod(s: Settings, broker, notifier, journal: Journal) -> None:
    """Day trading = no overnight: near the close, flatten any open stock positions."""
    if s.profile_name == "crypto":
        return
    now_et = dt.datetime.now(ET)
    if now_et.weekday() >= 5 or not (now_et.hour == 15 and now_et.minute >= 55):
        return
    try:
        positions = broker.positions()
        if positions:
            broker.close_all_positions()
            if notifier:
                notifier.send(f"⏹️ End of day — flattened {len(positions)} open position(s).")
            journal.log("info", f"eod flatten: {len(positions)} positions")
    except Exception as e:  # noqa: BLE001
        journal.log("error", f"eod flatten: {e}")


def scan_once(
    s: Settings,
    broker,
    notifier,
    journal: Journal,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> list[dict]:
    """One pass over the watchlist. Returns the actions taken (or would take)."""
    actions: list[dict] = []
    profile = s.profile
    tf = profile.get("timeframe", "5Min")
    sessions = _sessions_for(s)

    now = pd.Timestamp(dt.datetime.now(dt.timezone.utc))
    if not force and not any(in_session(now, [x]) for x in sessions):
        return actions  # outside the trading window -> do nothing

    equity = broker.equity() if broker else 100_000.0
    strat = s.strategy

    for symbol in profile["symbols"]:
        try:
            if broker and broker.has_position(symbol):
                continue

            bars = _recent_bars(s, symbol, tf, days=3)
            if bars.empty or len(bars) < 30:
                continue

            day_key = bars.index.tz_convert(ET).normalize()
            groups = list(bars.groupby(day_key))
            if len(groups) < 2:
                continue
            prev, today = groups[-2][1], groups[-1][1]
            pdh, pdl = float(prev["high"].max()), float(prev["low"].min())

            hist = bars[bars.index < today.index[0]]
            htf = hist.resample("1h").agg(_AGG).dropna()

            signals = find_trades(
                today,
                levels=[pdh, pdl],
                htf_bars=htf if len(htf) >= 5 else None,
                pivot_strength=int(strat.get("pivot_strength", 2)),
                fvg_atr_mult=float(strat.get("fvg_atr_mult", 0.25)),
                atr_period=int(strat.get("atr_period", 14)),
                confirm_window=int(strat.get("confirm_window", 10)),
                min_rr=float(strat.get("min_rr", 2.0)),
                sessions=list(sessions),
                use_bias=True,
            )
            # only act on a signal that completed on the most recent closed bar(s)
            fresh = [sig for sig in signals if sig.index >= len(today) - 2]
            if not fresh:
                continue
            sig = max(fresh, key=lambda x: x.index)

            rc = RiskConfig.from_settings(s)
            rc.allow_fractional = "/" in symbol
            plan = plan_trade(symbol, sig, equity, rc)
            if plan is None:
                continue

            date = today.index[-1].tz_convert(ET).strftime("%Y%m%d")
            coid = f"tjr-{symbol.replace('/', '')}-{date}-{sig.index}"
            if journal.has_order(coid) or (broker is not None and broker.order_exists(coid)):
                continue

            action = {
                "symbol": symbol, "side": plan.side, "entry": round(plan.entry, 2),
                "stop": round(plan.stop, 2), "target": round(plan.target, 2),
                "qty": round(plan.qty, 4), "coid": coid, "reasons": plan.reasons,
            }

            if dry_run or broker is None:
                action["status"] = "dry-run"
            else:
                order = broker.submit_bracket(plan, coid)
                journal.record_order(
                    coid, str(order.id), symbol, plan.side, plan.entry, plan.stop,
                    plan.target, plan.qty, str(order.status), plan.reasons,
                )
                action["status"] = str(order.status)
                if notifier:
                    notifier.send(_format_alert(plan, str(order.status)))
            actions.append(action)
        except Exception as e:  # noqa: BLE001 - never let one symbol kill the loop
            journal.log("error", f"{symbol}: {e}")
            continue

    return actions


def cycle(s: Settings, broker, notifier, journal: Journal, *, force: bool = False) -> list[dict]:
    """One full pass: reconcile closed trades, flatten at EOD, then scan for new setups.

    Safe to call on a schedule (e.g. GitHub Actions) — idempotent via Alpaca order ids.
    """
    if broker is not None:
        reconcile(broker, journal)
        flatten_if_eod(s, broker, notifier, journal)
    return scan_once(s, broker, notifier, journal, force=force)


def run_forever(s: Settings, interval: int = 60, force: bool = False) -> None:
    from .execution.alpaca_exec import Broker
    from .notify.telegram import TelegramNotifier

    broker = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)
    notifier = TelegramNotifier(s.telegram_token, s.telegram_chat_id)
    journal = Journal()
    notifier.send("🤖 <b>TJR bot started</b> (paper). Watching the market for setups…")
    journal.log("info", "bot started")

    while True:
        try:
            for a in cycle(s, broker, notifier, journal, force=force):
                print(a)
        except Exception as e:  # noqa: BLE001
            journal.log("error", f"loop: {e}")
        time.sleep(interval)
