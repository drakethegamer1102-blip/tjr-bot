#!/usr/bin/env python3
"""Autonomous every-other-day strategy review.

Pulls closed trades from Alpaca, computes per-strategy PF/expectancy/drawdown,
compares to baseline, and proposes evidence-gated config tweaks.

Usage:
    python scripts/review_bot.py          # print report + proposed changes
    python scripts/review_bot.py --apply  # apply approved changes to config.yaml

Never touches risk rails (max_position_pct, daily_max_loss_pct, etc.).
Paper-only safeguard: aborts if ALPACA_PAPER != "true".
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
import yaml

# ── safety ────────────────────────────────────────────────────────────────────
if os.getenv("ALPACA_PAPER", "").lower() != "true":
    sys.exit("review_bot: ALPACA_PAPER != true — aborting (paper only)")

api = TradingClient(
    os.environ["ALPACA_API_KEY_ID"],
    os.environ["ALPACA_API_SECRET"],
    paper=True,
)

RISK_RAILS = {
    "max_position_pct", "daily_max_loss_pct", "daily_max_losses",
    "daily_max_trades", "max_concurrent_positions", "max_position_loss_pct",
}

LOOKBACK_DAYS = 14  # analyse last 2 weeks of trades
MIN_TRADES = 5      # need at least this many per strategy to draw conclusions


# ── data ──────────────────────────────────────────────────────────────────────
def fetch_closed_trades(days: int = LOOKBACK_DAYS) -> list[dict]:
    """Reconstruct completed round-trips from Alpaca closed orders.

    Strategy: entry orders have bot-/tjr- client_order_ids. Exit legs
    (TP/stop) have UUID cids. Match them by symbol + filled_at proximity
    (exit must fill within EXIT_WINDOW_HOURS after entry).
    """
    EXIT_WINDOW_HOURS = 24

    since = datetime.now(timezone.utc) - timedelta(days=days)
    req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=since, limit=500)
    orders = api.get_orders(req)

    def _ts(o) -> datetime | None:
        v = o.filled_at
        if v is None:
            return None
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except Exception:
            return None

    def _side(o) -> str:
        return o.side.value if hasattr(o.side, "value") else str(o.side)

    # Separate entries (tagged) from exit candidates (UUID cid, opposite side)
    entries, exits = [], []
    for o in orders:
        qty = float(o.filled_qty or 0)
        price = float(o.filled_avg_price or 0)
        if qty <= 0 or price <= 0:
            continue
        cid = o.client_order_id or ""
        if cid.startswith("bot-") or cid.startswith("tjr-"):
            entries.append(o)
        else:
            exits.append(o)

    trades = []
    used_exits: set[str] = set()

    for entry in entries:
        cid = entry.client_order_id or ""
        if cid.startswith("bot-"):
            strat = cid.split("-")[1]
        else:
            strat = "tjr"

        entry_side = _side(entry)
        entry_price = float(entry.filled_avg_price)
        entry_qty = float(entry.filled_qty)
        entry_ts = _ts(entry)
        if entry_ts is None:
            continue

        # Exit is opposite side, same symbol, fills after entry within window
        exit_side = "buy" if entry_side == "sell" else "sell"
        best = None
        for ex in exits:
            if str(ex.id) in used_exits:
                continue
            if ex.symbol != entry.symbol:
                continue
            if _side(ex) != exit_side:
                continue
            ex_ts = _ts(ex)
            if ex_ts is None:
                continue
            delta = (ex_ts - entry_ts).total_seconds() / 3600
            if 0 <= delta <= EXIT_WINDOW_HOURS:
                if best is None or ex_ts < _ts(best):
                    best = ex

        if best is None:
            continue

        used_exits.add(str(best.id))
        exit_price = float(best.filled_avg_price)

        pnl = (exit_price - entry_price) * entry_qty if entry_side == "buy" \
              else (entry_price - exit_price) * entry_qty

        trades.append({
            "strategy": strat,
            "symbol": entry.symbol,
            "pnl": pnl,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "qty": entry_qty,
            "filled_at": str(entry_ts),
        })

    return trades


def compute_pnl(trades: list[dict]) -> list[dict]:
    return trades


def per_strategy_stats(pnl_rows: list[dict]) -> dict[str, dict]:
    from collections import defaultdict
    agg: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "gross_win": 0.0, "gross_loss": 0.0, "trades": []})
    for r in pnl_rows:
        s = agg[r["strategy"]]
        s["trades"].append(r["pnl"])
        if r["pnl"] >= 0:
            s["wins"] += 1
            s["gross_win"] += r["pnl"]
        else:
            s["losses"] += 1
            s["gross_loss"] += abs(r["pnl"])

    stats = {}
    for strat, s in agg.items():
        n = s["wins"] + s["losses"]
        pf = s["gross_win"] / s["gross_loss"] if s["gross_loss"] > 0 else float("inf")
        exp = (s["gross_win"] - s["gross_loss"]) / n if n else 0
        # max drawdown from equity curve
        curve = [0.0]
        for p in s["trades"]:
            curve.append(curve[-1] + p)
        peak = curve[0]
        mdd = 0.0
        for v in curve:
            if v > peak:
                peak = v
        for v in curve:
            dd = peak - v
            mdd = max(mdd, dd)
        stats[strat] = {
            "n": n,
            "win_pct": s["wins"] / n * 100 if n else 0,
            "pf": pf,
            "expectancy": exp,
            "total_pnl": s["gross_win"] - s["gross_loss"],
            "max_drawdown": mdd,
        }
    return stats


# ── proposals ─────────────────────────────────────────────────────────────────
def propose_changes(stats: dict[str, dict], cfg: dict) -> list[dict]:
    """Evidence-gated proposals. Only suggests changes with >= MIN_TRADES data."""
    proposals = []

    for strat, s in stats.items():
        if s["n"] < MIN_TRADES:
            continue

        # Disable a consistently losing strategy (PF < 0.8 over 2 weeks)
        strat_cfg = (cfg.get("strategies") or {}).get(strat, {})
        enabled = strat_cfg.get("enabled", True) if isinstance(strat_cfg, dict) else True
        if s["pf"] < 0.8 and enabled:
            proposals.append({
                "key": f"strategies.{strat}.enabled",
                "old": True,
                "new": False,
                "reason": f"{strat}: PF {s['pf']:.2f} < 0.80 over {s['n']} trades → disable",
            })

        # Re-enable a disabled strategy if it's now profitable
        if s["pf"] > 1.2 and not enabled:
            proposals.append({
                "key": f"strategies.{strat}.enabled",
                "old": False,
                "new": True,
                "reason": f"{strat}: PF {s['pf']:.2f} > 1.20 over {s['n']} trades → re-enable",
            })

        # vwap_rev: tune atr_mult if max drawdown is high relative to total pnl
        if strat == "vwap_rev" and s["n"] >= MIN_TRADES:
            current_mult = (strat_cfg or {}).get("atr_mult", 2.0) if isinstance(strat_cfg, dict) else 2.0
            if s["max_drawdown"] > abs(s["total_pnl"]) * 2 and current_mult > 1.5:
                proposals.append({
                    "key": "strategies.vwap_rev.atr_mult",
                    "old": current_mult,
                    "new": round(current_mult - 0.25, 2),
                    "reason": f"vwap_rev: max_drawdown ${s['max_drawdown']:.0f} >> total_pnl ${s['total_pnl']:.0f} → tighten atr_mult",
                })

    return proposals


def apply_proposals(proposals: list[dict], cfg: dict) -> dict:
    """Apply proposals to config dict. Never touches RISK_RAILS."""
    for p in proposals:
        key = p["key"]
        if any(rail in key for rail in RISK_RAILS):
            print(f"  SKIPPED (risk rail): {key}")
            continue
        parts = key.split(".")
        node = cfg
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = p["new"]
    return cfg


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply approved proposals to config.yaml")
    parser.add_argument("--days", type=int, default=LOOKBACK_DAYS)
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  TJR BOT — AUTONOMOUS REVIEW   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Lookback: {args.days} days | Min trades for signal: {MIN_TRADES}")
    print(f"{'='*60}\n")

    trades = fetch_closed_trades(args.days)
    print(f"Fetched {len(trades)} closed fills from Alpaca\n")

    if not trades:
        print("No trades found in window — nothing to review.")
        return

    pnl_rows = compute_pnl(trades)
    stats = per_strategy_stats(pnl_rows)

    print(f"{'Strategy':<12} {'N':>4} {'Win%':>6} {'PF':>6} {'Exp/trade':>10} {'Total P&L':>11} {'MaxDD':>9}")
    print("-" * 62)
    for strat, s in sorted(stats.items()):
        pf_str = f"{s['pf']:.2f}" if s['pf'] != float("inf") else "∞"
        print(f"{strat:<12} {s['n']:>4} {s['win_pct']:>5.1f}% {pf_str:>6} "
              f"${s['expectancy']:>8.0f} ${s['total_pnl']:>9.0f} ${s['max_drawdown']:>7.0f}")

    cfg_path = ROOT / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    proposals = propose_changes(stats, cfg)

    print(f"\n{'─'*60}")
    if not proposals:
        print("No changes proposed — performance within acceptable range.")
    else:
        print(f"PROPOSED CHANGES ({len(proposals)}):")
        for i, p in enumerate(proposals, 1):
            print(f"  {i}. {p['key']}: {p['old']} → {p['new']}")
            print(f"     Reason: {p['reason']}")

    if args.apply and proposals:
        print(f"\nApplying {len(proposals)} proposal(s) to config.yaml...")
        cfg = apply_proposals(proposals, cfg)
        with open(cfg_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        print("Done. Run tests to verify: pytest trading-bot/")
    elif proposals:
        print("\nRun with --apply to apply these changes.")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
