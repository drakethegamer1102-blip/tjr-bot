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
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)


class Broker:
    def __init__(self, key: str, secret: str, paper: bool = True):
        self.tc = TradingClient(key, secret, paper=paper)

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
    def submit_bracket(self, plan, client_order_id: str, tif: TimeInForce = TimeInForce.DAY):
        """Submit a bracket order: market entry when plan.entry_type=='market', else limit."""
        is_crypto = "/" in plan.symbol
        qty = plan.qty if is_crypto else int(plan.qty)
        if not is_crypto and qty < 1:
            raise ValueError(f"{plan.symbol}: position rounds to <1 share")

        side = OrderSide.BUY if plan.side == "long" else OrderSide.SELL
        tp = TakeProfitRequest(limit_price=round(plan.target, 2))
        sl = StopLossRequest(stop_price=round(plan.stop, 2))

        if getattr(plan, "entry_type", "limit") == "market":
            req = MarketOrderRequest(
                symbol=plan.symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
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
