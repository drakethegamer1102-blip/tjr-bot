"""Watch the bot scan the market right now (read-only — places no orders).

For each screened symbol it shows the bot's current read: daily bias, how many
liquidity sweeps / market-structure-shifts / fair-value-gaps it sees today, and
whether a full TJR signal is firing. Also shows account + any open positions.
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from tjrbot.config import load_settings
from tjrbot.data.alpaca_data import get_crypto_bars, get_stock_bars
from tjrbot.engine import _AGG, _resolve_symbols, _sessions_for
from tjrbot.execution.alpaca_exec import Broker
from tjrbot.journal import Journal
from tjrbot.smc.session import ET, in_session
from tjrbot.smc.structure import detect_structure
from tjrbot.smc.zones import find_fvgs, find_sweeps
from tjrbot.strategy import daily_bias, find_trades

BIAS = {1: "bull", -1: "bear", 0: "neutral"}


def main() -> int:
    s = load_settings()
    journal = Journal()
    broker = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)
    strat = s.strategy
    tf = s.profile.get("timeframe", "5Min")
    sessions = _sessions_for(s)

    now_et = dt.datetime.now(ET)
    market_open = now_et.weekday() < 5 and dt.time(9, 30) <= now_et.time() <= dt.time(16, 0)
    session_active = any(in_session(pd.Timestamp(dt.datetime.now(dt.timezone.utc)), [x]) for x in sessions)

    acct = broker.account()
    equity, last_eq = float(acct.equity), float(acct.last_equity or acct.equity)

    print("=" * 64)
    print(f"  TJR BOT — LIVE SCAN   {now_et:%Y-%m-%d %H:%M:%S ET}")
    print(f"  Market: {'OPEN' if market_open else 'CLOSED'}   "
          f"Entry window active: {'YES' if session_active else 'no'} ({'/'.join(sessions)})")
    print(f"  Equity: ${equity:,.2f}   Today P&L: ${equity - last_eq:+,.2f}")
    print("=" * 64)

    positions = broker.positions()
    print(f"\nOPEN POSITIONS: {len(positions)}")
    pos_out = []
    for p in positions:
        side = str(p.side.value).upper()
        entry, cur, upl = float(p.avg_entry_price), float(p.current_price), float(p.unrealized_pl)
        uplpc = float(p.unrealized_plpc) * 100
        print(f"  {p.symbol:6} {side:5} qty {p.qty}  entry ${entry:.2f}  now ${cur:.2f}  "
              f"P&L ${upl:+,.2f} ({uplpc:+.1f}%)")
        pos_out.append({"symbol": p.symbol, "side": side, "qty": str(p.qty),
                        "entry": entry, "current": cur, "upl": upl, "uplpc": uplpc})
    if not positions:
        print("  (flat — no open positions)")

    symbols = _resolve_symbols(s, s.profile, journal)
    print(f"\nSCANNING {len(symbols)} symbols (screened universe + watchlist):")
    print(f"  {symbols}\n")
    print(f"  {'SYMBOL':7} {'BIAS':8} {'SWEEP':6} {'MSS':4} {'FVG':4}  READ")
    print("  " + "-" * 60)

    scanned = []
    for sym in symbols:
        try:
            bars = (get_crypto_bars if "/" in sym else get_stock_bars)(
                s.alpaca_key, s.alpaca_secret, sym, tf, 3
            )
            if bars.empty or len(bars) < 30:
                print(f"  {sym:7} {'-':8} {'-':6} {'-':4} {'-':4}  no data")
                scanned.append({"symbol": sym, "bias": "-", "signal": None, "note": "no data"})
                continue
            day_key = bars.index.tz_convert(ET).normalize()
            groups = list(bars.groupby(day_key))
            prev, today = groups[-2][1], groups[-1][1]
            pdh, pdl = float(prev["high"].max()), float(prev["low"].min())
            hist = bars[bars.index < today.index[0]]
            htf = hist.resample("1h").agg(_AGG).dropna()

            ps = int(strat.get("pivot_strength", 2))
            bias = daily_bias(htf, ps) if len(htf) >= 5 else 0
            n_sweep = len(find_sweeps(today, [pdh, pdl]))
            n_mss = len([e for e in detect_structure(today, ps) if e.kind == "MSS"])
            n_fvg = len(find_fvgs(today, float(strat.get("fvg_atr_mult", 0.25)), int(strat.get("atr_period", 14))))
            sigs = find_trades(
                today, [pdh, pdl], htf_bars=htf if len(htf) >= 5 else None,
                pivot_strength=ps, fvg_atr_mult=float(strat.get("fvg_atr_mult", 0.25)),
                atr_period=int(strat.get("atr_period", 14)),
                confirm_window=int(strat.get("confirm_window", 10)),
                min_rr=float(strat.get("min_rr", 2.0)), sessions=list(sessions), use_bias=True,
            )
            sig_obj = None
            if sigs:
                g = sigs[-1]
                read = f"** {g.side.upper()} setup  entry ${g.entry:.2f} stop ${g.stop:.2f} tgt ${g.target:.2f}"
                sig_obj = {"side": g.side, "entry": round(g.entry, 2), "stop": round(g.stop, 2), "target": round(g.target, 2)}
            else:
                read = "watching — no qualifying setup"
            print(f"  {sym:7} {BIAS[bias]:8} {n_sweep:<6} {n_mss:<4} {n_fvg:<4}  {read}")
            scanned.append({"symbol": sym, "bias": BIAS[bias], "sweeps": n_sweep,
                            "mss": n_mss, "fvg": n_fvg, "signal": sig_obj})
        except Exception as e:  # noqa: BLE001
            print(f"  {sym:7} scan error: {e}")
            scanned.append({"symbol": sym, "bias": "-", "signal": None, "note": str(e)})

    live = [x for x in scanned if x.get("signal")]
    print("\n" + "=" * 64)
    print(f"  RESULT: {len(live)} live setup(s) across {len(symbols)} symbols.")
    if not live and not session_active:
        print("  Entry window is closed, so the bot would not act on a setup now.")
    print("=" * 64)

    result = {
        "time_et": now_et.strftime("%Y-%m-%d %H:%M:%S ET"),
        "market_open": market_open, "session_active": session_active, "sessions": list(sessions),
        "equity": equity, "today_pl": equity - last_eq,
        "positions": pos_out, "scanned": scanned, "live_setups": len(live),
    }
    print("JSON_RESULT=" + json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
