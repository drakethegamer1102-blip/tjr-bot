"""Historical / recent OHLCV bars from Alpaca, returned as a clean DataFrame.

Output: a single-symbol DataFrame indexed by tz-aware UTC timestamp with columns
[open, high, low, close, volume] — exactly what the SMC engine expects.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import (
    CryptoHistoricalDataClient,
    StockHistoricalDataClient,
)
from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

_TF = {
    "1Min": TimeFrame(1, TimeFrameUnit.Minute),
    "5Min": TimeFrame(5, TimeFrameUnit.Minute),
    "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    "30Min": TimeFrame(30, TimeFrameUnit.Minute),
    "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
    "4Hour": TimeFrame(4, TimeFrameUnit.Hour),
    "1Day": TimeFrame(1, TimeFrameUnit.Day),
}

_COLS = ["open", "high", "low", "close", "volume"]


def _parse_tf(s: str) -> TimeFrame:
    return _TF.get(s, _TF["5Min"])


def _clean(df: pd.DataFrame | None, symbol: str) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=_COLS)
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level="symbol")
    df = df[[c for c in _COLS if c in df.columns]].copy()
    df.index = pd.to_datetime(df.index, utc=True)
    return df.sort_index()


def get_stock_bars(
    key: str,
    secret: str,
    symbol: str,
    timeframe: str = "5Min",
    days: int = 30,
    feed: DataFeed = DataFeed.SIP,
) -> pd.DataFrame:
    """Fetch bars using SIP (real-time) if the plan allows it, falling back to IEX (15-min delay)."""
    client = StockHistoricalDataClient(key, secret)
    # SIP: data is available up to ~1 min ago; IEX needs a 16-min buffer.
    end_sip = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    end_iex = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=16)

    def _fetch(f: DataFeed, end: dt.datetime) -> pd.DataFrame:
        start = end - dt.timedelta(days=days)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=_parse_tf(timeframe),
            start=start,
            end=end,
            feed=f,
        )
        return _clean(client.get_stock_bars(req).df, symbol)

    if feed == DataFeed.SIP:
        try:
            return _fetch(DataFeed.SIP, end_sip)
        except Exception:
            # Free plan: SIP not allowed — fall back to IEX silently.
            return _fetch(DataFeed.IEX, end_iex)
    return _fetch(feed, end_iex)


def get_crypto_bars(
    key: str,
    secret: str,
    symbol: str,
    timeframe: str = "15Min",
    days: int = 30,
) -> pd.DataFrame:
    client = CryptoHistoricalDataClient(key, secret)
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(days=days)
    req = CryptoBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=_parse_tf(timeframe),
        start=start,
        end=end,
    )
    return _clean(client.get_crypto_bars(req).df, symbol)
