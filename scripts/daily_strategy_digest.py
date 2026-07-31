"""Daily per-strategy digest — sends SEPARATE Telegram messages, one per product,
each breaking down exactly which strategy traded today and whether it made money.

Three independent messages (never merged):
  🟢 LIVE   · today's stock-account trades, grouped by strategy, win/loss each
  📈 FUTURES DAILY · DAYBREAK / REBOUND / GAPFILL today, win/loss each
  📈 FUTURES ORB   · intraday micro-futures today, win/loss each

Each message shows: strategy · #trades · $P&L · WIN/LOSS, then the day's net. A product
with no trades today sends a one-line "no trades" note (so you always know it ran).

Usage:
    python scripts/daily_strategy_digest.py            # today, send all three
    python scripts/daily_strategy_digest.py --date 2026-07-31
    python scripts/daily_strategy_digest.py --no-telegram
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tjrbot.config import load_settings
from tjrbot.execution.alpaca_exec import Broker
from tjrbot.reconcile import compute_pnl

try:
    from tjrbot.notify.telegram import TelegramNotifier
except Exception:
    TelegramNotifier = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent


def _verdict(pnl: float) -> str:
    return "🟢 WIN" if pnl > 0 else "🔴 LOSS" if pnl < 0 else "⚪ flat"


def _trade_line(t: dict) -> str:
    """One expanded line per trade: symbol, side, entry→exit, qty, P&L, verdict, reason."""
    sym = t.get("sym", "")
    side = (t.get("side") or "").upper()
    entry = t.get("entry"); exit_ = t.get("exit"); qty = t.get("qty")
    px = ""
    if entry is not None and exit_ is not None:
        px = f" {entry:g}→{exit_:g}"
    q = f" ×{qty:g}" if qty else ""
    exitk = f" [{t['exit_kind']}]" if t.get("exit_kind") else ""
    note = f" — {t['note']}" if t.get("note") else ""
    head = f"    • {sym} {side}{q}{px}".rstrip()
    return f"{head}  <b>${t['pnl']:+,.0f}</b> {_verdict(t['pnl'])}{exitk}{note}"


def _fmt_day(rows: list[dict], header: str, empty_note: str) -> str:
    """rows: [{strat, pnl, ...trade detail}] for one day. Expanded: each strategy lists its
    trades one per line (symbol, side, entry→exit, qty, P&L), then a per-strategy subtotal,
    then the day net."""
    if not rows:
        return f"{header}\n  {empty_note}"
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["strat"]].append(r)
    net = sum(r["pnl"] for r in rows)
    lines = [header]
    # strategies ordered by their subtotal (winners first)
    for st in sorted(by, key=lambda k: -sum(r["pnl"] for r in by[k])):
        trs = by[st]
        sub = sum(r["pnl"] for r in trs)
        lines.append(f"  <b>{st}</b> · {len(trs)}t · ${sub:+,.0f}  {_verdict(sub)}")
        for t in trs:
            lines.append(_trade_line(t))
    lines.append(f"  ── day net <b>${net:+,.0f}</b>  {_verdict(net)}")
    return "\n".join(lines)


def _live_rows(broker, day: str) -> list[dict]:
    """Today's closed stock round-trips, one row per fill, tagged by strategy."""
    out = []
    try:
        orders = broker.closed_orders(limit=500)
    except Exception:
        return out
    for o in orders:
        coid = getattr(o, "client_order_id", "") or ""
        parts = coid.split("-")
        st = None
        if coid.startswith(("apx-", "rip-", "bot-")) and len(parts) > 1:
            st = parts[1]
        elif coid.startswith("tjr-"):
            st = "tjr"
        if st is None:
            continue
        entry = getattr(o, "filled_avg_price", None)
        if not entry:
            continue
        legs = getattr(o, "legs", None) or []
        ex = next((l for l in legs if "filled" in str(getattr(l, "status", "")).lower()
                   and getattr(l, "filled_avg_price", None)), None)
        if ex is None:
            continue
        when = str(getattr(ex, "filled_at", None) or getattr(o, "filled_at", "") or "")[:10]
        if when != day:
            continue
        side = "long" if str(getattr(o, "side", "")).lower().endswith("buy") else "short"
        qty = float(getattr(o, "filled_qty", 0) or 0)
        xpx = float(ex.filled_avg_price)
        pnl = compute_pnl(side, float(entry), xpx, qty)
        out.append({"strat": st, "pnl": pnl, "sym": getattr(o, "symbol", ""),
                    "side": side, "entry": round(float(entry), 2), "exit": round(xpx, 2),
                    "qty": qty})
    return out


def _ledger_rows(path: Path, day: str, kind: str) -> list[dict]:
    if not path.exists():
        return []
    d = json.loads(path.read_text())
    out = []
    if kind in ("daily", "stock"):  # {STRAT: {trades:[{day,side,entry,exit,pnl,note}]}}
        sym = "SPY" if kind == "stock" else "MES"
        for name, book in d.items():
            for t in book.get("trades", []):
                if t.get("day") == day:
                    out.append({"strat": name, "pnl": t["pnl"], "side": t.get("side"),
                                "entry": t.get("entry"), "exit": t.get("exit"),
                                "note": t.get("note"), "sym": sym})
    else:                 # orb futures: {trades:[{day,symbol,side,contracts,entry,exit,exit_kind,pnl}]}
        for t in d.get("trades", []):
            if t.get("day") == day:
                out.append({"strat": t.get("symbol", "?"), "pnl": t["pnl"],
                            "sym": t.get("symbol", ""), "side": t.get("side"),
                            "entry": t.get("entry"), "exit": t.get("exit"),
                            "qty": t.get("contracts"), "exit_kind": t.get("exit_kind")})
    return out


def main(argv: list[str]) -> int:
    day = argv[argv.index("--date") + 1] if "--date" in argv else \
        datetime.now(timezone.utc).strftime("%Y-%m-%d")
    send = "--no-telegram" not in argv
    s = load_settings()
    broker = Broker(s.alpaca_key, s.alpaca_secret, paper=s.alpaca_paper)

    messages = [
        _fmt_day(_live_rows(broker, day),
                 f"🟢 <b>LIVE · stocks</b> (real account) — {day}",
                 "no live trades today."),
        _fmt_day(_ledger_rows(ROOT / "stock_daily_ledger.json", day, "stock"),
                 f"🟢 <b>STOCK · DAILY</b> (paper · DIPSNAP/PULLBACK/TUESDAY-EQ) — {day}",
                 "no stock-daily setups today."),
        _fmt_day(_ledger_rows(ROOT / "futures_daily_ledger.json", day, "daily"),
                 f"📈 <b>FUTURES · DAILY</b> (paper · 6 strategies) — {day}",
                 "no futures-daily setups today."),
        _fmt_day(_ledger_rows(ROOT / "orb_futures_ledger.json", day, "orb"),
                 f"📈 <b>FUTURES · ORB</b> (paper · intraday micro) — {day}",
                 "no ORB-futures trades today."),
    ]

    tg = TelegramNotifier(s.telegram_token, s.telegram_chat_id) if (send and TelegramNotifier and s.telegram_token) else None
    for m in messages:
        print(m.replace("<b>", "").replace("</b>", ""), "\n")
        if tg:
            tg.send(m)          # SEPARATE message per product
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
