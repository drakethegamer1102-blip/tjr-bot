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

import copy
import datetime as dt
import time

import pandas as pd

from .config import Settings
from .data.alpaca_data import get_crypto_bars, get_stock_bars
from .journal import Journal
from .risk.engine import RiskConfig, daily_loss_exceeded, plan_trade
from .reconcile import compute_pnl, reconcile
from .regime import filter_signals, market_bias, market_filter
from .smc.session import ET, in_session
from .strategy import daily_bias, find_trades
from .strategies import NEEDS_HIST, REGISTRY

_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}

# Act on a signal only if it completed within the last FRESH_BARS closed bars. Keeps
# entries near real time (no chasing stale setups) while tolerating the gap between a
# bar closing and the next 5-min scan firing. 3 bars ≈ last 15 min on 5-min data.
FRESH_BARS = 3

# Every client_order_id prefix this engine has ever written. "bot-" = legacy single-bot
# era, "tjr-" = pre-multi-strategy era, "apx-"/"rip-" = the APEX and RIPTIDE virtual
# bots (2026-07-08). Order-history scans (halts, summaries, reconcile) match on these.
BOT_PREFIXES = ("bot-", "tjr-", "apx-", "rip-")


def _recent_bars(s: Settings, symbol: str, tf: str, days: int = 3) -> pd.DataFrame:
    if "/" in symbol:
        return get_crypto_bars(s.alpaca_key, s.alpaca_secret, symbol, tf, days)
    return get_stock_bars(s.alpaca_key, s.alpaca_secret, symbol, tf, days)


def _sessions_for(s: Settings) -> tuple[str, ...]:
    return ("ny", "london") if s.profile_name == "crypto" else ("ny_open", "ny_pm")


def _market_bias_today(s: Settings, tf: str, proxy: str = "SPY") -> int:
    """Broad-market bias for today from the index proxy (SPY). +1 risk-on / -1
    risk-off / 0 unclear. Best-effort: any error -> 0 (filter simply doesn't apply)."""
    try:
        bars = _recent_bars(s, proxy, tf, days=2)
        if bars.empty:
            return 0
        day_key = bars.index.tz_convert(ET).normalize()
        today = list(bars.groupby(day_key))[-1][1]
        return market_bias(today, min_pct=float(s.get("market_bias_min_pct", 0.25)))
    except Exception:  # noqa: BLE001
        return 0


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


def cancel_late_entries(s: Settings, broker, journal: Journal, cutoff_hour: int = 15,
                        cutoff_min: int = 30) -> None:
    """Cancel still-open bot ENTRY orders after the cutoff (default 15:30 ET).

    A limit entry that fills in the last 30 min has no time to work before the EOD
    flatten force-closes it — a near-guaranteed scratch/loss. (2026-06-18: a MRVL
    limit submitted 11:00 finally filled at 15:50, then was flattened at 15:55.)
    Cancelling late keeps the signal from becoming a dead-on-arrival trade. Only
    cancels parent ENTRY orders that are still open and unfilled; live bracket exits
    on already-filled positions are untouched.
    """
    if s.profile_name == "crypto":
        return
    now_et = dt.datetime.now(ET)
    past_cutoff = (now_et.hour == cutoff_hour and now_et.minute >= cutoff_min) or now_et.hour > cutoff_hour
    if now_et.weekday() >= 5 or not past_cutoff:
        return
    try:
        canceled = 0
        for o in broker.open_orders():
            cid = getattr(o, "client_order_id", "") or ""
            if not cid.startswith(BOT_PREFIXES):
                continue
            # Only unfilled parent entries (skip anything already partially/fully filled).
            if float(getattr(o, "filled_qty", 0) or 0) > 0:
                continue
            broker.cancel(o.id)
            canceled += 1
        if canceled:
            journal.log("info", f"late-entry cancel: dropped {canceled} unfilled entry order(s) after {cutoff_hour}:{cutoff_min:02d}")
    except Exception as e:  # noqa: BLE001
        journal.log("error", f"late-entry cancel: {e}")


def flatten_if_eod(s: Settings, broker, notifier, journal: Journal) -> None:
    """Day trading = no overnight: in the final minutes of the REGULAR session, flatten
    any open stock positions while market orders can still fill.

    Window is 15:50-16:00 ET ONLY. Before 15:50 we're still trading; at/after 16:00 the
    market is closed, so a SELL MARKET just gets canceled and the position stays open —
    and the old "hour >= 16" window re-fired that on every 5-min scan, spamming a
    Telegram each time and never actually closing anything (2026-06-30: dozens of
    "End of day flattened" alerts, 3 positions left open). Overnight safety after a
    missed window is covered by GTC brackets + flatten_stale_positions at next open.

    Also: only notify when a close was actually submitted, and verify positions exist
    AFTER the close call so a no-op never alerts.
    """
    if s.profile_name == "crypto":
        return
    now_et = dt.datetime.now(ET)
    if now_et.weekday() >= 5:
        return
    minutes = now_et.hour * 60 + now_et.minute
    REG_OPEN = 15 * 60 + 45    # 15:45 — start trying while the regular session is open
    CLOSE = 16 * 60           # 16:00
    AH_CUTOFF = 19 * 60 + 45  # 19:45 — last safe time to queue an extended-hours exit
    in_regular_window = REG_OPEN <= minutes < CLOSE
    in_afterhours_window = CLOSE <= minutes < AH_CUTOFF
    if not (in_regular_window or in_afterhours_window):
        return
    try:
        positions = broker.positions()
        if not positions:
            return  # nothing to do -> no notification (kills the post-close spam)
        if in_regular_window:
            # Market still open: plain market exit fills immediately.
            broker.close_all_positions()
            n = len(positions)
        else:
            # Market closed: a DAY market order would just cancel. Use extended-hours
            # marketable LIMIT orders so the position ACTUALLY exits in after-hours.
            # Skip if an after-hours exit (eodx-) is already pending, so a later scan
            # doesn't stack duplicate orders (and doesn't re-notify).
            try:
                pending_ah = any(
                    (getattr(o, "client_order_id", "") or "").startswith("eodx-")
                    for o in broker.open_orders()
                )
            except Exception:  # noqa: BLE001
                pending_ah = False
            if pending_ah:
                return
            n = broker.close_all_positions_extended_hours()
        if n:
            when = "EOD" if in_regular_window else "after-hours"
            if notifier:
                notifier.send(f"⏹️ {when} flatten — closing {n} open position(s).")
            journal.log("info", f"{when} flatten: {n} positions")
    except Exception as e:  # noqa: BLE001
        journal.log("error", f"eod flatten: {e}")


def flatten_stale_positions(s: Settings, broker, notifier, journal: Journal) -> None:
    """Backstop: close any position opened on a PRIOR day.

    This is the safety net for a missed EOD flatten (cron drift, an outage, a boundary
    run). A day-trading bot must never hold overnight; if a stale position is found at
    the next session's first scan, close it immediately rather than carrying naked risk
    (its DAY-TIF protective bracket has already expired). Crypto is exempt (24/7).
    """
    if s.profile_name == "crypto":
        return
    try:
        positions = broker.positions()
    except Exception as e:  # noqa: BLE001
        journal.log("error", f"stale-position check: {e}")
        return
    today = dt.datetime.now(ET).date()
    closed = 0
    for p in positions:
        # Find the most recent fill for this symbol to learn when it was opened.
        try:
            opened_today = _position_opened_today(broker, p.symbol, today)
        except Exception:  # noqa: BLE001
            opened_today = True  # on doubt, do NOT close (avoid churning a fresh entry)
        if not opened_today:
            try:
                broker.close_position(p.symbol)
                closed += 1
                journal.log("info", f"stale flatten: closed overnight {p.symbol} qty={p.qty}")
            except Exception as e:  # noqa: BLE001
                journal.log("error", f"stale flatten {p.symbol}: {e}")
    if closed and notifier:
        notifier.send(f"⚠️ Closed {closed} stale overnight position(s) at session open.")


def _position_opened_today(broker, symbol: str, today) -> bool:
    """True if the symbol's open position was entered today (ET). Checks the most
    recent filled bot entry order for the symbol."""
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5)
    req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=since, limit=200,
                           symbols=[symbol.replace("/", "")])
    orders = broker.tc.get_orders(filter=req)
    latest_fill = None
    for o in orders:
        if "filled" not in str(getattr(o, "status", "")).lower():
            continue
        fa = getattr(o, "filled_at", None)
        if fa and (latest_fill is None or fa > latest_fill):
            latest_fill = fa
    if latest_fill is None:
        return True  # unknown -> treat as fresh (don't churn)
    return latest_fill.astimezone(ET).date() == today


def _daily_halt(s: Settings, broker) -> str | None:
    """Persistent daily risk gate — works across stateless scheduled runs via the live account.

    Returns a reason to stop opening new trades today, or None to proceed.
    """
    try:
        acct = broker.account()
        eq = float(acct.equity)
        last_eq = float(acct.last_equity) if acct.last_equity else eq
    except Exception:  # noqa: BLE001
        return None
    if daily_loss_exceeded(eq, last_eq, float(s.get("daily_max_loss_pct", 0.05))):
        return f"daily loss limit ({(eq - last_eq) / last_eq * 100:.1f}%)"
    try:
        today = dt.datetime.now(ET).date()
        # Count LOGICAL trades, not orders: partial-TP submits two brackets per
        # trade (coid-a / coid-b), so collapse to the coid stem before counting.
        stems: set[str] = set()
        loss_stems: set[str] = set()
        for o in broker.closed_orders(limit=500):
            coid = getattr(o, "client_order_id", "") or ""
            # tjr- was the legacy prefix; counting it too keeps the gate airtight
            if not coid.startswith(("bot-", "tjr-")) or "filled" not in str(getattr(o, "status", "")).lower():
                continue
            fa = getattr(o, "filled_at", None)
            if not (fa and fa.astimezone(ET).date() == today):
                continue
            stem = coid[:-2] if coid.endswith(("-a", "-b")) else coid
            stems.add(stem)
            # Realized loss check via nested bracket legs: a filled exit leg worse
            # than entry = a realized losing trade. (closed_orders uses nested=True.)
            entry_px = float(getattr(o, "filled_avg_price", 0) or 0)
            side = str(getattr(o, "side", "")).lower()
            for leg in (getattr(o, "legs", None) or []):
                if "filled" not in str(getattr(leg, "status", "")).lower():
                    continue
                exit_px = float(getattr(leg, "filled_avg_price", 0) or 0)
                if not (entry_px and exit_px):
                    continue
                pnl = (exit_px - entry_px) if side.endswith("buy") else (entry_px - exit_px)
                if pnl < 0:
                    loss_stems.add(stem)
                break
        if len(stems) >= int(s.get("daily_max_trades", 4)):
            return f"daily trade cap ({len(stems)} trades)"
        if len(loss_stems) >= int(s.get("daily_max_losses", 3)):
            return f"daily loss-count cap ({len(loss_stems)} losing trades)"
    except Exception:  # noqa: BLE001
        pass
    return None


def _bot_of_map(s: Settings) -> dict[str, str]:
    """strategy name -> bot name, for strategies assigned to a virtual bot."""
    cfg = s.raw.get("strategies") or {}
    return {name: c["bot"] for name, c in cfg.items()
            if isinstance(c, dict) and c.get("bot")}


def _bot_halts(s: Settings, broker) -> set[str]:
    """Per-bot daily gates (trade count / loss count / realized daily loss).

    Each virtual bot (config `bots:`) has its own envelope, enforced from the live
    account's closed orders by coid prefix — stateless across scheduled runs, same
    pattern as _daily_halt. The ACCOUNT-level 5% halt in _daily_halt still overrides
    everything; these are sub-limits so one bot can't spend the whole day's risk.
    """
    bots = s.raw.get("bots") or {}
    if not bots or broker is None:
        return set()
    try:
        eq = float(broker.account().equity)
        orders = broker.closed_orders(limit=500)
    except Exception:  # noqa: BLE001
        return set()
    today = dt.datetime.now(ET).date()
    pref_to_bot = {str((c or {}).get("prefix", n)): n for n, c in bots.items()}
    stems: dict[str, set] = {n: set() for n in bots}
    loss_stems: dict[str, set] = {n: set() for n in bots}
    pnl: dict[str, float] = {n: 0.0 for n in bots}
    for o in orders:
        coid = getattr(o, "client_order_id", "") or ""
        bot = pref_to_bot.get(coid.split("-", 1)[0]) if "-" in coid else None
        if bot is None or "filled" not in str(getattr(o, "status", "")).lower():
            continue
        fa = getattr(o, "filled_at", None)
        if not (fa and fa.astimezone(ET).date() == today):
            continue
        stem = coid[:-2] if coid.endswith(("-a", "-b")) else coid
        stems[bot].add(stem)
        entry_px = float(getattr(o, "filled_avg_price", 0) or 0)
        side = str(getattr(o, "side", "")).lower()
        qty = float(getattr(o, "filled_qty", 0) or 0)
        for leg in (getattr(o, "legs", None) or []):
            if "filled" not in str(getattr(leg, "status", "")).lower():
                continue
            exit_px = float(getattr(leg, "filled_avg_price", 0) or 0)
            if not (entry_px and exit_px):
                continue
            per_share = (exit_px - entry_px) if side.endswith("buy") else (entry_px - exit_px)
            pnl[bot] += per_share * qty
            if per_share < 0:
                loss_stems[bot].add(stem)
            break
    halted: set[str] = set()
    for name, c in bots.items():
        c = c or {}
        if len(stems[name]) >= int(c.get("daily_max_trades", 8)):
            halted.add(name)
        elif len(loss_stems[name]) >= int(c.get("daily_max_losses", 4)):
            halted.add(name)
        elif eq > 0 and pnl[name] < -float(c.get("daily_max_loss_pct", 0.025)) * eq:
            halted.add(name)
    return halted


def _collect_signals(s: Settings, today, pdh, pdl, htf, sessions, strat, journal=None,
                     symbol="?", mkt_bias=0, hist=None) -> list:
    """Run every enabled strategy for one symbol's session; return tagged signals."""
    cfg = s.raw.get("strategies") or {"tjr": {"enabled": True}}
    out: list = []
    if (cfg.get("tjr") or {}).get("enabled", True):
        use_htf = htf is not None and len(htf) >= 5
        bias = daily_bias(htf, int(strat.get("pivot_strength", 2))) if use_htf else 0
        bias_label = {1: "BULLISH", -1: "BEARISH", 0: "NEUTRAL"}[bias]
        if journal:
            journal.log("info", f"{symbol}: HTF bias={bias_label} pdh={pdh:.2f} pdl={pdl:.2f} htf_bars={len(htf) if use_htf else 0}")
        out += find_trades(
            today, [pdh, pdl], htf_bars=htf if use_htf else None,
            pivot_strength=int(strat.get("pivot_strength", 2)),
            fvg_atr_mult=float(strat.get("fvg_atr_mult", 0.25)),
            atr_period=int(strat.get("atr_period", 14)),
            confirm_window=int(strat.get("confirm_window", 20)),
            min_rr=float(strat.get("min_rr", 3.0)),
            sessions=list(sessions), use_bias=True,
        )
    for name, gen in REGISTRY.items():
        c = cfg.get(name) or {}
        if not c.get("enabled", False):
            continue
        params = {k: v for k, v in c.items() if k not in ("enabled", "bot")}
        if name in NEEDS_HIST:
            params["hist"] = hist
        try:
            sigs = gen(today, **params)
        except Exception:  # noqa: BLE001
            sigs = []
        out += [sg for sg in sigs if in_session(today.index[sg.index], list(sessions))]
    if s.get("regime_filter", False):  # off by default — backtest showed it removes profitable fades
        out = filter_signals(out, today)
    # Broad-market gate: never short on a clearly risk-on day, never long on a
    # clearly risk-off day (the 2026-06-18 TSLA/MSFT-short-into-a-green-day fix).
    if s.get("market_filter", True) and mkt_bias != 0:
        before = len(out)
        out = market_filter(out, mkt_bias)
        if journal and len(out) < before:
            mb = {1: "risk-on", -1: "risk-off"}[mkt_bias]
            journal.log("info", f"{symbol}: market_filter ({mb}) dropped {before - len(out)} counter-market signal(s)")
    return out


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
    if broker is not None:
        # Backstop first: never carry a position opened on a prior day.
        flatten_stale_positions(s, broker, notifier, journal)
        halt = _daily_halt(s, broker)
        if halt:
            journal.log("info", f"trading halted for today: {halt}")
            return actions
        if len(broker.positions()) >= int(s.get("max_concurrent_positions", 3)):
            return actions
    strat = s.strategy
    symbols = _resolve_symbols(s, profile, journal)
    bot_of = _bot_of_map(s)
    bots_cfg = s.raw.get("bots") or {}
    halted_bots = _bot_halts(s, broker) if broker is not None else set()
    if halted_bots:
        journal.log("info", f"bot envelope halt(s) today: {', '.join(sorted(halted_bots))}")

    # Compute the broad-market bias ONCE per scan (SPY today's bars) and reuse it for
    # every symbol's market_filter. Crypto profile has no equity index -> 0 (off).
    mkt_bias = _market_bias_today(s, tf) if s.profile_name != "crypto" else 0
    if mkt_bias != 0:
        journal.log("info", f"market bias today = {'risk-on' if mkt_bias == 1 else 'risk-off'}")

    for symbol in symbols:
        try:
            if broker and broker.has_position(symbol):
                continue
            # Don't stack a second bracket on a symbol whose entry is still pending.
            # (June 12: a few entries sat UNFILLED/EXPIRED for 20+ min; without this
            # guard a later scan could double up before the first resolved.)
            if broker and broker.has_open_order(symbol):
                continue

            # 16 days of history: the last 2 day-groups drive intraday levels, the
            # full window gives daily_bias a real HTF swing structure to read, and
            # noise_band needs 14 prior sessions for its time-of-day sigma bands.
            # (Pre-2026-06-13 this was days=3 → ~13 hourly bars → bias was noise, which
            #  produced June 11's all-short loss day.)
            bars = _recent_bars(s, symbol, tf, days=16)
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

            signals = _collect_signals(s, today, pdh, pdl, htf, sessions, strat, journal=journal, symbol=symbol, mkt_bias=mkt_bias, hist=hist)
            # Per-bot envelope: drop signals from bots that hit their daily gates.
            if halted_bots:
                signals = [sg for sg in signals if bot_of.get(sg.strategy) not in halted_bots]
            # Act on signals that completed on a recent closed bar. Keep the freshest
            # signal PER STRATEGY (not just the single global latest) so momentum /
            # macd_trend / squeeze — whose crossovers fire mid-session — actually get
            # submitted instead of always losing the tie to whichever strategy printed
            # last. (Pre-2026-06-18: a single `max(fresh)` meant the new strategies
            # generated dozens of signals but almost never traded.)
            fresh = [sig for sig in signals if sig.index >= len(today) - FRESH_BARS]
            if not fresh:
                continue
            freshest_by_strat: dict[str, "Signal"] = {}
            for sig in fresh:
                cur = freshest_by_strat.get(sig.strategy)
                if cur is None or sig.index > cur.index:
                    freshest_by_strat[sig.strategy] = sig

            date = today.index[-1].tz_convert(ET).strftime("%Y%m%d")
            # One position per symbol at a time: if we already hold/ordered the symbol,
            # don't stack a second strategy's entry on it this scan.
            for sig in sorted(freshest_by_strat.values(), key=lambda x: x.index, reverse=True):
                if broker is not None and (broker.has_position(symbol) or broker.has_open_order(symbol)):
                    break
                bot_name = bot_of.get(sig.strategy)
                bot_cfg = (bots_cfg.get(bot_name) or {}) if bot_name else None
                act = _submit_signal(s, broker, notifier, journal, symbol, sig, today,
                                     date, equity, dry_run, bot_cfg=bot_cfg)
                if act is not None:
                    actions.append(act)
        except Exception as e:  # noqa: BLE001 - never let one symbol kill the loop
            journal.log("error", f"{symbol}: {e}")
            continue

    return actions


def _submit_signal(s, broker, notifier, journal, symbol, sig, today, date, equity, dry_run,
                   bot_cfg=None):
    """Size + risk-check + submit one signal as a (partial-TP) bracket. Returns the
    action dict, or None if it was skipped."""
    rc = RiskConfig.from_settings(s).with_bot_overrides(bot_cfg)
    rc.allow_fractional = "/" in symbol
    plan = plan_trade(symbol, sig, equity, rc)
    if plan is None:
        return None
    if plan.side == "short" and broker is not None and not broker.is_shortable(symbol):
        journal.log("info", f"{symbol}: short setup skipped (not shortable)")
        return None

    prefix = (bot_cfg or {}).get("prefix", "bot")
    coid = f"{prefix}-{sig.strategy}-{symbol.replace('/', '')}-{date}-{sig.index}"
    if journal.has_order(coid) or (broker is not None and broker.order_exists(coid)):
        return None

    # Partial-TP: split into two brackets when we have enough shares.
    # Leg A: half qty, TP at 1R (lock-in quick profit). Leg B: half, full target.
    # OFF by default (2026-06-23): the two halves share one stop, so a stop-out loses
    # BOTH halves fully while a win caps the first half at 1R — a strictly worse payoff
    # than a single full-target bracket (live: NVDA/MSFT pairs both stopped together).
    # Backtest shows no benefit, and it adds live order-management fragility. Re-enable
    # only with breakeven-stop management on the runner. Toggle via config `partial_tp`.
    is_crypto = "/" in symbol
    use_partial = bool(s.get("partial_tp", False)) and (not is_crypto) and int(plan.qty) >= 2
    risk = abs(plan.entry - plan.stop)
    tp_quick = (plan.entry + risk) if plan.side == "long" else (plan.entry - risk)

    if use_partial:
        half = int(plan.qty) // 2
        remainder = int(plan.qty) - half
        leg_a = copy.copy(plan); leg_a.qty = half;      leg_a.target = round(tp_quick, 2)
        leg_b = copy.copy(plan); leg_b.qty = remainder; leg_b.target = plan.target
        legs = [(leg_a, f"{coid}-a"), (leg_b, f"{coid}-b")]
    else:
        legs = [(plan, coid)]

    action = {
        "symbol": symbol, "side": plan.side, "strategy": sig.strategy,
        "entry": round(plan.entry, 2), "stop": round(plan.stop, 2),
        "target": round(plan.target, 2), "qty": round(plan.qty, 4),
        "coid": coid, "reasons": plan.reasons, "partial_tp": use_partial,
    }

    if dry_run or broker is None:
        action["status"] = "dry-run"
        return action

    first_order = None
    for leg_plan, leg_coid in legs:
        if journal.has_order(leg_coid) or broker.order_exists(leg_coid):
            continue
        order = broker.submit_bracket(leg_plan, leg_coid)
        journal.record_order(
            leg_coid, str(order.id), symbol, leg_plan.side, leg_plan.entry,
            leg_plan.stop, leg_plan.target, leg_plan.qty,
            str(order.status), leg_plan.reasons,
        )
        if first_order is None:
            first_order = order
    action["status"] = str(first_order.status) if first_order else "already-recorded"
    if first_order is not None and notifier:
        notifier.send(_format_alert(plan, str(first_order.status)))
    return action


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

    pnls: list[float] = []          # all closed round-trips in the fetched window
    today_pnls: list[float] = []    # subset whose EXIT filled today (ET)
    for o in closed:
        coid = getattr(o, "client_order_id", "") or ""
        entry_px = getattr(o, "filled_avg_price", None)
        if not coid.startswith(BOT_PREFIXES) or not entry_px:
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
        pnls.append(pnl)
        fa = getattr(exit_leg, "filled_at", None)
        try:
            if fa and fa.astimezone(ET).date() == today:
                today_pnls.append(pnl)
        except Exception:  # noqa: BLE001
            pass

    # ── TODAY (realized, closed round-trips that exited today) ──────────────
    today_n = len(today_pnls)
    today_wins = sum(1 for p in today_pnls if p > 0)
    today_losses = sum(1 for p in today_pnls if p < 0)
    today_realized = sum(today_pnls)
    today_win_rate = (today_wins / today_n * 100) if today_n else 0.0

    # ── ALL-TIME (everything in the fetched window) ────────────────────────
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
        f"Account P&L today: ${today_pl:+,.2f} ({today_pct:+.2f}%)  "
        f"<i>(incl. open positions)</i>\n"
        f"Open positions: {open_pos}\n\n"
        f"<b>Today's closed trades:</b>\n"
        f"{today_n} trade(s)  |  {today_win_rate:.0f}% win ({today_wins}W/{today_losses}L)\n"
        f"Realized today: ${today_realized:+,.2f}\n\n"
        f"<b>All-time (paper, last {n} closed):</b>\n"
        f"Win rate: {win_rate:.0f}% ({wins}W/{losses}L)\n"
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
        if not coid.startswith(BOT_PREFIXES) or not entry_px:
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
        cancel_late_entries(s, broker, journal)   # drop unfilled entries before the close
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
