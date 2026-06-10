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
from .reconcile import compute_pnl, reconcile
from .smc.session import ET, in_session
from .strategy import find_trades

_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _recent_bars(s: Settings, symbol: str, tf: str, days: int = 3) -> pd.DataFrame:
    if "/" in symbol:
        return get_crypto_bars(s.alpaca_key, s.alpaca_secret, symbol, tf, days)
    return get_stock_bars(s.alpaca_key, s.alpaca_secret, symbol, tf, days)


def _sessions_for(s: Settings) -> tuple[str, ...]:
    return ("ny", "london") if s.profile_name == "crypto" else ("ny_open", "ny_pm")


def _resolve_symbols(s: Settings, profile: dict, journal: Journal) -> list[str]:
    """The symbols to scan: the watchlist, plus a screened universe if enabled."""
    watchlist = list(profile.get("symbols", []))
    uni = profile.get("universe") or {}
    if not uni.get("enabled") or s.profile_name != "stocks":
        return watchlist
    try:
        from .data.screener import get_candidates

        return get_candidates(
            s.alpaca_key,
            s.alpaca_secret,
            max_symbols=int(uni.get("max_symbols", 20)),
            min_price=float(uni.get("min_price", 5)),
            max_price=float(uni.get("max_price", 1000)),
            extra=watchlist,
        )
    except Exception as e:  # noqa: BLE001
        journal.log("error", f"screener: {e}")
        return watchlist


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
    symbols = _resolve_symbols(s, profile, journal)

    for symbol in symbols:
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


def daily_summary(s: Settings, broker, notifier, journal: Journal) -> str:
    """Build and send an end-of-day Telegram report (even on no-trade days).

    Alpaca is the source of truth, so this works fine in stateless cloud runs.
    """
    reconcile(broker, journal)
    acct = broker.account()
    eq = float(acct.equity)
    last = float(acct.last_equity or eq)
    today_pl = eq - last
    today_pct = (today_pl / last * 100) if last else 0.0
    today = dt.datetime.now(ET).date()

    try:
        closed = broker.closed_orders(limit=200)
    except Exception as e:  # noqa: BLE001
        journal.log("error", f"summary fetch: {e}")
        closed = []

    pnls: list[float] = []
    today_n = 0
    for o in closed:
        coid = getattr(o, "client_order_id", "") or ""
        entry_px = getattr(o, "filled_avg_price", None)
        if not coid.startswith("tjr-") or not entry_px:
            continue
        legs = getattr(o, "legs", None) or []
        exit_leg = next(
            (leg for leg in legs if "filled" in str(getattr(leg, "status", "")).lower()
             and getattr(leg, "filled_avg_price", None)),
            None,
        )
        if exit_leg is None:
            continue
        side = "long" if str(getattr(o, "side", "")).lower().endswith("buy") else "short"
        pnls.append(compute_pnl(side, float(entry_px), float(exit_leg.filled_avg_price),
                                float(getattr(o, "filled_qty", 0) or 0)))
        fa = getattr(exit_leg, "filled_at", None)
        try:
            if fa and fa.astimezone(ET).date() == today:
                today_n += 1
        except Exception:  # noqa: BLE001
            pass

    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    win_rate = (wins / n * 100) if n else 0.0
    net = sum(pnls)
    try:
        open_pos = len(broker.positions())
    except Exception:  # noqa: BLE001
        open_pos = 0

    emoji = "📈" if today_pl >= 0 else "📉"
    headline = "No setups today — stayed flat." if today_n == 0 else f"Took {today_n} trade(s) today."
    msg = (
        f"{emoji} <b>Daily summary — {today:%a %b %d}</b>\n"
        f"{headline}\n\n"
        f"Equity: ${eq:,.2f}\n"
        f"Today's P&L: ${today_pl:+,.2f} ({today_pct:+.2f}%)\n"
        f"Open positions: {open_pos}\n\n"
        f"<b>All-time (paper):</b>\n"
        f"Trades: {n}  |  Win rate: {win_rate:.0f}% ({wins}W/{losses}L)\n"
        f"Net P&L: ${net:+,.2f}"
    )
    if notifier:
        notifier.send(msg)
    return msg


def _closed_bot_trades(broker, journal: Journal) -> list[dict]:
    """Every closed bracket the bot has placed, as {'symbol','pnl','dt'(ET)} rows."""
    try:
        closed = broker.closed_orders(limit=200)
    except Exception as e:  # noqa: BLE001
        journal.log("error", f"summary fetch: {e}")
        return []
    rows: list[dict] = []
    for o in closed:
        coid = getattr(o, "client_order_id", "") or ""
        entry_px = getattr(o, "filled_avg_price", None)
        if not coid.startswith("tjr-") or not entry_px:
            continue
        legs = getattr(o, "legs", None) or []
        exit_leg = next(
            (leg for leg in legs if "filled" in str(getattr(leg, "status", "")).lower()
             and getattr(leg, "filled_avg_price", None)),
            None,
        )
        if exit_leg is None:
            continue
        side = "long" if str(getattr(o, "side", "")).lower().endswith("buy") else "short"
        pnl = compute_pnl(side, float(entry_px), float(exit_leg.filled_avg_price),
                          float(getattr(o, "filled_qty", 0) or 0))
        fa = getattr(exit_leg, "filled_at", None)
        try:
            when = fa.astimezone(ET) if fa else None
        except Exception:  # noqa: BLE001
            when = None
        rows.append({"symbol": getattr(o, "symbol", ""), "pnl": pnl, "dt": when})
    return rows


def summarize_trades(trades: list[dict]) -> dict:
    """Pure aggregation over [{'symbol','pnl','dt'}] rows (count, win rate, best/worst)."""
    pnls = [t["pnl"] for t in trades]
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / n * 100) if n else 0.0,
        "net": sum(pnls),
        "best": max(trades, key=lambda t: t["pnl"]) if trades else None,
        "worst": min(trades, key=lambda t: t["pnl"]) if trades else None,
    }


def weekly_summary(s: Settings, broker, notifier, journal: Journal) -> str:
    """Send a Friday recap of the week's trading to Telegram."""
    reconcile(broker, journal)
    now = dt.datetime.now(ET)
    monday = (now - dt.timedelta(days=now.weekday())).date()
    week = [t for t in _closed_bot_trades(broker, journal) if t["dt"] and t["dt"].date() >= monday]
    w = summarize_trades(week)
    try:
        eq = float(broker.account().equity)
    except Exception:  # noqa: BLE001
        eq = 0.0

    def fmt(label: str, t: dict | None) -> str:
        return f"{label}: {t['symbol']} ${t['pnl']:+,.0f}" if t else f"{label}: —"

    headline = "No trades this week." if not week else f"{w['n']} trade(s) this week."
    msg = (
        f"🗓️ <b>Weekly recap — week of {monday:%b %d}</b>\n{headline}\n\n"
        f"Week P&L: ${w['net']:+,.2f}\n"
        f"Win rate: {w['win_rate']:.0f}% ({w['wins']}W/{w['losses']}L)\n"
        f"{fmt('Best', w['best'])}\n{fmt('Worst', w['worst'])}\n\n"
        f"Equity: ${eq:,.2f}"
    )
    if notifier:
        notifier.send(msg)
    return msg


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
