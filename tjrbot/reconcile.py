"""Turn closed bracket orders into recorded win/loss trades (for the dashboard).

When a bracket fills and one exit leg (take-profit or stop-loss) executes, the
position is closed. We read those closed orders back from Alpaca, compute realised
P&L, and store it in the journal. Idempotent: each setup is recorded only once.
"""

from __future__ import annotations


def compute_pnl(side: str, entry: float, exit_: float, qty: float) -> float:
    return (exit_ - entry) * qty if side == "long" else (entry - exit_) * qty


def _filled(status) -> bool:
    return "filled" in str(status).lower()


def reconcile(broker, journal, *, limit: int = 200) -> int:
    """Record any newly-closed bot trades. Returns how many were added."""
    try:
        orders = broker.closed_orders(limit=limit)
    except Exception as e:  # noqa: BLE001
        journal.log("error", f"reconcile fetch: {e}")
        return 0

    recorded = 0
    for o in orders or []:
        coid = getattr(o, "client_order_id", None) or ""
        if not coid.startswith("bot-") or journal.has_trade(coid):
            continue
        entry_px = getattr(o, "filled_avg_price", None)
        if not _filled(getattr(o, "status", "")) or not entry_px:
            continue

        legs = getattr(o, "legs", None) or []
        exit_leg = next(
            (
                leg
                for leg in legs
                if _filled(getattr(leg, "status", "")) and getattr(leg, "filled_avg_price", None)
            ),
            None,
        )
        if exit_leg is None:
            continue  # entry filled but position not closed yet

        side = "long" if str(getattr(o, "side", "")).lower().endswith("buy") else "short"
        entry = float(entry_px)
        exit_ = float(exit_leg.filled_avg_price)
        qty = float(getattr(o, "filled_qty", 0) or 0)
        pnl = compute_pnl(side, entry, exit_, qty)
        win = (side == "long" and exit_ > entry) or (side == "short" and exit_ < entry)
        journal.record_trade(
            coid,
            getattr(o, "symbol", ""),
            side,
            entry,
            exit_,
            qty,
            pnl,
            "target" if win else "stop",
            str(getattr(o, "filled_at", "") or ""),
            str(getattr(exit_leg, "filled_at", "") or ""),
        )
        recorded += 1
    return recorded
