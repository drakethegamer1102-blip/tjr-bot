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


def _append_realtime_bar(
    df: pd.DataFrame, client: StockHistoricalDataClient, symbol: str,
    timeframe: str, feed: DataFeed,
) -> pd.DataFrame:
    """Extend `df` with a real-time 'current' bar built from the latest live trade.

    The historical-bars endpoint on IEX lags ~16 min, so the newest completed bar is
    stale. The latest-trade endpoint is real-time (seconds fresh) on the SAME free plan.
    We snap the live trade price to the current bar's timestamp bucket and append/merge it
    so every strategy sees price right up to NOW. Fail-open: any error -> return df
    unchanged (a scan must never crash on this).
    """
    try:
        from alpaca.data.requests import StockLatestTradeRequest
        tr = client.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=symbol, feed=feed))[symbol]
        price = float(tr.price)
        ts = pd.to_datetime(tr.timestamp, utc=True)
        if price <= 0 or df.empty:
            return df
        # bucket the live trade into the current timeframe bar (floor to the interval)
        tf = _parse_tf(timeframe)
        minutes = {"1Min": 1, "5Min": 5, "15Min": 15, "30Min": 30}.get(timeframe, 5)
        bucket = ts.floor(f"{minutes}min")
        if bucket <= df.index[-1]:
            # live trade falls inside the last known bar — just update its close/high/low
            last = df.iloc[-1]
            df.loc[df.index[-1], "high"] = max(float(last["high"]), price)
            df.loc[df.index[-1], "low"] = min(float(last["low"]), price)
            df.loc[df.index[-1], "close"] = price
        else:
            # a new forming bar since the last completed one
            df.loc[bucket] = {"open": price, "high": price, "low": price,
                              "close": price, "volume": 0.0}
        return df.sort_index()
    except Exception:
        return df


def get_stock_bars(
    key: str,
    secret: str,
    symbol: str,
    timeframe: str = "5Min",
    days: int = 30,
    feed: DataFeed = DataFeed.SIP,
    realtime: bool = True,
) -> pd.DataFrame:
    """Fetch recent bars, extended with a REAL-TIME current bar so strategies see price
    up to NOW — not the ~16-min-stale newest IEX historical bar.

    The historical-bars endpoint lags (IEX ~16 min; SIP ~1 min), but the latest-TRADE
    endpoint is real-time on the same plan. We fetch the completed bars, then append a
    live forming bar from the latest trade (`realtime=True`, the default). Pass
    `realtime=False` for backtests / when a purely-historical series is wanted.
    """
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
        df = _clean(client.get_stock_bars(req).df, symbol)
        if realtime:
            df = _append_realtime_bar(df, client, symbol, timeframe, f)
        return df

    if feed == DataFeed.SIP:
        try:
            return _fetch(DataFeed.SIP, end_sip)
        except Exception:
            # Free plan: SIP not allowed — fall back to IEX silently (still real-time via trade).
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
