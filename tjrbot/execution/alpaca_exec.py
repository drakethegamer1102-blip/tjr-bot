"""Alpaca paper-trading execution: bracket orders + account/position helpers.

A bracket order submits three linked legs at once: the entry, a take-profit, and a
stop-loss. Once the entry fills, Alpaca manages the exits, so the bot protects every
position even if the script or host goes down.
"""

from __future__ import annotations

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)


class Broker:
    def __init__(self, key: str, secret: str, paper: bool = True):
        self.tc = TradingClient(key, secret, paper=paper)
        self._key = key
        self._secret = secret

    # --- reads ---
    def account(self):
        return self.tc.get_account()

    def equity(self) -> float:
        return float(self.tc.get_account().equity)

    def positions(self):
        return self.tc.get_all_positions()

    def closed_orders(self, limit: int = 200):
        """Recently closed orders, with bracket legs nested."""
        req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=limit, nested=True)
        return self.tc.get_orders(filter=req)

    def has_position(self, symbol: str) -> bool:
        try:
            self.tc.get_open_position(symbol.replace("/", ""))
            return True
        except Exception:
            return False

    def open_orders(self, symbol: str | None = None):
        """All open (pending) orders, optionally filtered to one symbol."""
        req = GetOrdersRequest(
            status=QueryOrderStatus.OPEN,
            limit=200,
            symbols=[symbol.replace("/", "")] if symbol else None,
        )
        return self.tc.get_orders(filter=req)

    # Every client_order_id prefix the engine writes (mirror of engine.BOT_PREFIXES,
    # duplicated here so the execution layer never imports the engine). 2026-07-08:
    # apx-/rip- were missing, so the anti-stacking guard below ignored pending
    # APEX/RIPTIDE entries and a later scan could double up on the same symbol.
    BOT_ORDER_PREFIXES = ("bot-", "tjr-", "apx-", "rip-")

    def has_open_order(self, symbol: str) -> bool:
        """True if any pending bot order exists for the symbol (prevents stacking
        a second bracket on a symbol whose first entry hasn't filled yet)."""
        try:
            for o in self.open_orders(symbol):
                cid = o.client_order_id or ""
                if cid.startswith(self.BOT_ORDER_PREFIXES):
                    return True
        except Exception:
            pass
        return False

    def order_exists(self, client_order_id: str) -> bool:
        """True if Alpaca already has an order with this id (idempotency for stateless runs)."""
        try:
            self.tc.get_order_by_client_order_id(client_order_id)
            return True
        except Exception:
            return False

    def is_shortable(self, symbol: str) -> bool:
        """True if the asset can be sold short (skip the trade otherwise)."""
        try:
            a = self.tc.get_asset(symbol.replace("/", ""))
            return bool(getattr(a, "tradable", False)) and bool(getattr(a, "shortable", False))
        except Exception:
            return False

    # --- writes ---
    # Max distance a "market" entry may fill from the signal price, as a fraction of
    # entry. The stop/target are computed off the signal bar (free IEX data, ~15 min
    # delayed), so an uncapped market order can fill far enough away that the planned
    # stop sits pennies from the fill — live fills showed stops 0.08-0.5% from entry
    # despite a 1.5% floor (MSFT 06-23 stopped the same minute it entered; AAPL 07-01
    # stopped 0.54% below fill). A marketable LIMIT this far through the signal price
    # fills immediately when the live price is close, and simply doesn't fill (no
    # trade, no risk) when the market has already run away from the plan.
    ENTRY_SLIPPAGE_CAP = 0.003

    def submit_bracket(self, plan, client_order_id: str, tif: TimeInForce = TimeInForce.DAY):
        """Submit a bracket order. entry_type=='market' becomes a marketable limit
        capped ENTRY_SLIPPAGE_CAP through the signal price; else a plain limit."""
        is_crypto = "/" in plan.symbol
        qty = plan.qty if is_crypto else int(plan.qty)
        if not is_crypto and qty < 1:
            raise ValueError(f"{plan.symbol}: position rounds to <1 share")

        side = OrderSide.BUY if plan.side == "long" else OrderSide.SELL
        tp = TakeProfitRequest(limit_price=round(plan.target, 2))
        sl = StopLossRequest(stop_price=round(plan.stop, 2))

        if getattr(plan, "entry_type", "limit") == "market":
            cap = self.ENTRY_SLIPPAGE_CAP
            limit = plan.entry * (1 + cap) if plan.side == "long" else plan.entry * (1 - cap)
            req = LimitOrderRequest(
                symbol=plan.symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                limit_price=round(limit, 2),
                order_class=OrderClass.BRACKET,
                take_profit=tp,
                stop_loss=sl,
                client_order_id=client_order_id,
            )
        else:
            req = LimitOrderRequest(
                symbol=plan.symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                limit_price=round(plan.entry, 2),
                order_class=OrderClass.BRACKET,
                take_profit=tp,
                stop_loss=sl,
                client_order_id=client_order_id,
            )
        return self.tc.submit_order(req)

    def submit_test_limit(self, symbol: str, qty: float, limit_price: float, client_order_id: str):
        """A plain, non-marketable limit order — used only to verify the order path."""
        req = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            limit_price=limit_price,
            client_order_id=client_order_id,
        )
        return self.tc.submit_order(req)

    def cancel(self, order_id: str):
        return self.tc.cancel_order_by_id(order_id)

    def close_position(self, symbol: str):
        return self.tc.close_position(symbol.replace("/", ""))

    def close_all_positions(self):
        return self.tc.close_all_positions(cancel_orders=True)

    def close_all_positions_extended_hours(self, slippage_pct: float = 0.01):
        """Flatten every open position with EXTENDED-HOURS marketable limit orders.

        A plain market (or DAY market) order can only fill during the regular session,
        so after 16:00 it just cancels — that left positions open overnight and spammed
        the EOD alert (2026-06-30). Extended-hours orders run until 8pm ET, but Alpaca
        requires them to be LIMIT orders. We price each exit `slippage_pct` THROUGH the
        last trade (sell below / buy above) so it's marketable and actually fills.
        Returns the number of close orders submitted.
        """
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest

        positions = self.tc.get_all_positions()
        if not positions:
            return 0
        # cancel any stuck DAY exit orders first so they don't conflict
        try:
            self.tc.cancel_orders()
        except Exception:  # noqa: BLE001
            pass

        data = StockHistoricalDataClient(self._key, self._secret)
        submitted = 0
        for p in positions:
            sym = p.symbol
            qty = abs(int(float(p.qty)))
            if qty <= 0:
                continue
            is_long = str(p.side).lower().endswith("long")
            try:
                last = float(
                    data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=sym))[sym].price
                )
            except Exception:  # noqa: BLE001
                last = float(p.current_price or p.avg_entry_price)
            # marketable limit: sell a touch below last, buy a touch above
            limit = round(last * (1 - slippage_pct) if is_long else last * (1 + slippage_pct), 2)
            req = LimitOrderRequest(
                symbol=sym,
                qty=qty,
                side=OrderSide.SELL if is_long else OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=limit,
                extended_hours=True,
                client_order_id=f"eodx-{sym}-{int(qty)}-{limit}",
            )
            try:
                self.tc.submit_order(req)
                submitted += 1
            except Exception:  # noqa: BLE001
                continue
        return submitted
