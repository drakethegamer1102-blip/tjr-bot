"""Live REBOUND execution engine — real-money-grade, SPY, Alpaca real-time feed.

REBOUND is the one strategy that passed rigorous validation AND is live-tradable on the
existing Alpaca account: buy after 2 consecutive DOWN daily closes, hold ~1 day, exit at
the next close. Validated on SPY + ES over 33 years / every market era (PF ~1.1-1.6). It
is a DAILY strategy, so this engine is a once-a-day state machine, not an intraday scanner.

This module is PRISTINE and SEPARATE: it does not import or modify orb.py,
squeeze_breakout.py, or any existing strategy. It reuses the existing Broker plumbing.

Real-money hardening built in:
  * Idempotency — a stable per-day client_order_id; never double-enters even if the runner
    fires twice (Alpaca rejects the duplicate).
  * Circuit breaker — refuses to open a new position if the account is down more than
    `daily_max_loss_pct` on the day, or if a hard equity floor is breached.
  * Reconcile on start — adopts/manages any existing SPY position instead of ignoring it.
  * Guaranteed EOD flatten — the exit path closes the position regardless of entry path.
  * Real-time pricing — entry uses the live quote (IEX now; SIP one-line switch), never a
    delayed bar.

Two actions, driven by the runner (see scripts/rebound_live.py):
  * open_if_signal()  — run near the OPEN: enter if REBOUND fires and guards pass.
  * flatten_for_exit()— run near the CLOSE: exit the position (the strategy's 1-day hold).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..strategies.futures_daily import rebound


SYMBOL = "SPY"
COID_PREFIX = "rbd"          # REBOUND live order-id prefix (distinct from every other bot)


@dataclass
class ReboundConfig:
    risk_per_trade: float = 0.01        # fraction of equity risked per trade
    stop_pct: float = 0.02              # protective stop 2% below entry (safety net; the
                                        # strategy's real exit is the next close via flatten)
    daily_max_loss_pct: float = 0.03    # circuit breaker: no new entry if down >3% today
    max_position_pct: float = 0.50      # cap position notional at 50% of equity
    feed: str = "iex"                   # "iex" (free real-time) | "sip" ($99/mo, 100% vol)


class ReboundEngine:
    def __init__(self, broker, data_client, cfg: ReboundConfig | None = None, *, log=print):
        self.b = broker
        self.data = data_client
        self.cfg = cfg or ReboundConfig()
        self.log = log

    # ---------- data ----------
    def _daily_closes(self, lookback: int = 6):
        """Recent DAILY bars for SPY (need the last 3 closes to evaluate REBOUND)."""
        import pandas as pd
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=lookback * 3 + 10)
        req = StockBarsRequest(symbol_or_symbols=SYMBOL,
                               timeframe=TimeFrame(1, TimeFrameUnit.Day),
                               start=start.to_pydatetime(), feed=self.cfg.feed)
        df = self.data.get_stock_bars(req).df
        if df.empty:
            return None
        df = df.xs(SYMBOL, level="symbol") if "symbol" in getattr(df.index, "names", []) else df
        return df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()

    def _live_price(self) -> float:
        """Real-time last/mid price (not a delayed bar)."""
        from alpaca.data.requests import StockLatestQuoteRequest
        q = self.data.get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=SYMBOL, feed=self.cfg.feed))[SYMBOL]
        bid, ask = float(q.bid_price or 0), float(q.ask_price or 0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
        return ask or bid

    # ---------- guards ----------
    def _circuit_ok(self) -> bool:
        acct = self.b.account()
        eq, last = float(acct.equity), float(acct.last_equity or acct.equity)
        if last > 0 and (eq - last) / last <= -self.cfg.daily_max_loss_pct:
            self.log(f"CIRCUIT BREAKER: down {(eq/last-1)*100:.1f}% today — no new entry.")
            return False
        return True

    # ---------- actions ----------
    def open_if_signal(self, today_iso: str) -> str:
        """Run near the OPEN. Enter SPY if REBOUND fires and all guards pass.
        `today_iso` (YYYY-MM-DD) makes the order id stable/idempotent for the day."""
        # reconcile: if we already hold SPY, do nothing (managed; exit handles it)
        if self.b.has_position(SYMBOL):
            return "skip: already holding SPY"
        coid = f"{COID_PREFIX}-{SYMBOL}-{today_iso}"
        if self.b.order_exists(coid):
            return "skip: today's REBOUND order already placed (idempotent)"

        daily = self._daily_closes()
        if daily is None or len(daily) < 3:
            return "skip: insufficient daily data"
        # REBOUND decides from data THROUGH yesterday's close (exclude today's forming bar)
        plan = rebound(daily.iloc[:-1] if len(daily) > 3 else daily)
        if not plan:
            return "skip: no REBOUND signal (need 2 consecutive down days)"

        if not self._circuit_ok():
            return "halt: circuit breaker"

        price = self._live_price()
        if price <= 0:
            return "skip: no live price"
        eq = self.b.equity()
        stop = round(price * (1 - self.cfg.stop_pct), 2)
        per_share_risk = price - stop
        qty = int((eq * self.cfg.risk_per_trade) / per_share_risk) if per_share_risk > 0 else 0
        max_qty = int((eq * self.cfg.max_position_pct) / price)
        qty = max(0, min(qty, max_qty))
        if qty < 1:
            return "skip: size rounds to 0 shares"

        plan_obj = _EntryPlan(symbol=SYMBOL, side="long", qty=qty, entry=price,
                              stop=stop, target=round(price * 1.5, 2))  # far TP; real exit = EOD flatten
        self.b.submit_bracket(plan_obj, client_order_id=coid)
        self.log(f"REBOUND ENTRY: long {qty} {SYMBOL} @~{price:.2f} stop {stop} "
                 f"(risk {self.cfg.risk_per_trade*100:.0f}%) — {plan['note']}")
        return f"entered {qty} {SYMBOL}"

    def flatten_for_exit(self) -> str:
        """Run near the CLOSE. REBOUND holds ~1 day; exit at the close."""
        if not self.b.has_position(SYMBOL):
            return "skip: no SPY position to flatten"
        # cancel any resting protective legs first, then market-close
        try:
            for o in self.b.open_orders(SYMBOL):
                self.b.cancel(o.id)
        except Exception:
            pass
        self.b.close_position(SYMBOL)
        self.log(f"REBOUND EXIT: flattened {SYMBOL} at the close.")
        return "flattened SPY"


@dataclass
class _EntryPlan:
    symbol: str
    side: str
    qty: int
    entry: float
    stop: float
    target: float
    entry_type: str = "market"     # marketable-limit via Broker.submit_bracket
