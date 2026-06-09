"""Find tradable candidate stocks each scan ("go out and find stocks").

Pulls the day's most-active names + biggest movers from Alpaca's screener, then
keeps only liquid, reasonably-priced ordinary stocks — dropping penny stocks,
absurdly-priced names, and leveraged/inverse ETFs (which don't behave like normal
equities). So the strategy hunts where the real action is, not a fixed list.
"""

from __future__ import annotations

from alpaca.data.enums import DataFeed, MostActivesBy
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.screener import ScreenerClient
from alpaca.data.requests import (
    MarketMoversRequest,
    MostActivesRequest,
    StockSnapshotRequest,
)

# Leveraged / inverse ETFs move 2-3x and mean-revert oddly — skip them.
LEVERAGED_ETFS = {
    "TQQQ", "SQQQ", "SOXL", "SOXS", "TNA", "TZA", "SPXL", "SPXS", "UPRO", "SPXU",
    "UDOW", "SDOW", "LABU", "LABD", "TECL", "TECS", "FAS", "FAZ", "YINN", "YANG",
    "NUGT", "DUST", "JNUG", "JDST", "BOIL", "KOLD", "UCO", "SCO", "UVXY", "SVXY",
    "TMF", "TMV", "WEBL", "WEBS", "NAIL", "DRN", "DRV", "ERX", "ERY", "GUSH", "DRIP",
}


def rank_candidates(
    vol_by_sym: dict[str, float],
    price_by_sym: dict[str, float],
    *,
    min_price: float,
    max_price: float,
    max_symbols: int,
    deny: set[str] = LEVERAGED_ETFS,
) -> list[str]:
    """Pure filter+rank: keep ordinary stocks in the price band, sort by volume."""
    scored: list[tuple[float, str]] = []
    for sym, vol in vol_by_sym.items():
        if sym in deny or not sym.isalpha() or not (1 <= len(sym) <= 5):
            continue
        price = price_by_sym.get(sym)
        if price is None or not (min_price <= price <= max_price):
            continue
        scored.append((price * vol, sym))  # rank by DOLLAR volume = real liquidity
    scored.sort(reverse=True)
    return [sym for _, sym in scored[:max_symbols]]


def get_candidates(
    key: str,
    secret: str,
    *,
    max_symbols: int = 20,
    min_price: float = 5.0,
    max_price: float = 1000.0,
    extra: list[str] | None = None,
    feed: DataFeed = DataFeed.IEX,
) -> list[str]:
    """Return up to `max_symbols` screened tickers, with `extra` (watchlist) kept first."""
    sc = ScreenerClient(key, secret)
    vol_by_sym: dict[str, float] = {}
    price_by_sym: dict[str, float] = {}

    for by in (MostActivesBy.TRADES, MostActivesBy.VOLUME):
        try:
            for x in sc.get_most_actives(MostActivesRequest(top=60, by=by)).most_actives:
                v = float(getattr(x, "volume", 0) or 0)
                vol_by_sym[x.symbol] = max(vol_by_sym.get(x.symbol, 0.0), v)
        except Exception:  # noqa: BLE001
            pass
    try:
        mv = sc.get_market_movers(MarketMoversRequest(top=25))
        for g in list(mv.gainers) + list(mv.losers):
            vol_by_sym.setdefault(g.symbol, 0.0)
            if getattr(g, "price", None):
                price_by_sym[g.symbol] = float(g.price)
    except Exception:  # noqa: BLE001
        pass

    candidates = [s for s in vol_by_sym if s not in price_by_sym]
    if candidates:
        try:
            data = StockHistoricalDataClient(key, secret)
            snaps = data.get_stock_snapshot(
                StockSnapshotRequest(symbol_or_symbols=candidates, feed=feed)
            )
            for sym, snap in snaps.items():
                if snap is None:
                    continue
                lt = getattr(snap, "latest_trade", None)
                db = getattr(snap, "daily_bar", None)
                price = None
                if lt is not None and getattr(lt, "price", None):
                    price = float(lt.price)
                elif db is not None and getattr(db, "close", None):
                    price = float(db.close)
                if price:
                    price_by_sym[sym] = price
        except Exception:  # noqa: BLE001
            pass

    ranked = rank_candidates(
        vol_by_sym, price_by_sym,
        min_price=min_price, max_price=max_price, max_symbols=max_symbols,
    )
    # Always keep the explicit watchlist, listed first, then the screened names.
    return list(dict.fromkeys(list(extra or []) + ranked))
