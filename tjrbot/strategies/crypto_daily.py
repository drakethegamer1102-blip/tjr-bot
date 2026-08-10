"""Three DAILY crypto strategies — validated on BTC + ETH (2014-2026 / 2017-2026).

Crypto is the one asset class where momentum/breakout genuinely works (unlike stocks and
index futures, where it doesn't) — it's a trending, less-efficient, 24/7 market. Each of
these is a pre-specified published edge, validated robust across every era with data, and
the three are DISTINCT (BREAKOUT vs the two dip-buys have 0% trigger overlap). Alpaca
trades BTC/USD + ETH/USD, so these can go live on the existing account (no PDT rules, 24/7).

Same interface as the other *_daily strategies:
  decide(daily) -> dict | None   # daily bars oldest->newest, incl. today's bar
    {"name","side","entry_ref","exit","note"}

See CRYPTO_STRATEGY_RESEARCH.md. All long-biased (crypto's edge is on the long side).
"""

from __future__ import annotations

import pandas as pd


def _sma(s: pd.Series, n: int) -> float:
    return float(s.iloc[-n:].mean()) if len(s) >= n else float("nan")


def _rsi2(close: pd.Series) -> float:
    if len(close) < 4:
        return float("nan")
    delta = close.diff()
    up = delta.clip(lower=0)
    dn = (-delta).clip(lower=0)
    ru = up.ewm(alpha=0.5, adjust=False).mean()
    rd = dn.ewm(alpha=0.5, adjust=False).mean().replace(0, 1e-9)
    return float((100 - 100 / (1 + ru / rd)).iloc[-1])


# ---- MOONSHOT: 20-day-high breakout in an uptrend (momentum — crypto trends hard) ----
# Validated BTC+ETH PF 1.83. Buy a fresh 20-day high while Close > 200d SMA. Distinct
# (0% overlap with the dip strategies). Crypto momentum persists where stock breakouts fail.
def moonshot(daily: pd.DataFrame, *, hh_len: int = 20, sma_len: int = 200) -> dict | None:
    if len(daily) < sma_len:
        return None
    close = daily["close"]
    prior_high = float(daily["high"].iloc[-(hh_len + 1):-1].max())
    if float(close.iloc[-1]) >= prior_high and float(close.iloc[-1]) > _sma(close, sma_len):
        return {"name": "MOONSHOT", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"{hh_len}d-high breakout in uptrend"}
    return None


# ---- CRYPTODIP: 10-day-low pullback in a golden-cross uptrend ----
# Validated BTC+ETH PF 1.77. Buy a fresh 10-day low while 50d SMA > 200d SMA. High-quality
# dip in a confirmed uptrend.
def cryptodip(daily: pd.DataFrame, *, low_len: int = 10, fast: int = 50, slow: int = 200) -> dict | None:
    if len(daily) < slow:
        return None
    close = daily["close"]
    prior_low = float(daily["low"].iloc[-(low_len + 1):-1].min())
    if float(close.iloc[-1]) <= prior_low and _sma(close, fast) > _sma(close, slow):
        return {"name": "CRYPTODIP", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"{low_len}d-low dip in golden-cross uptrend"}
    return None


# ---- CRYPTORSI: RSI(2) deeply oversold in an uptrend (Connors, crypto edition) ----
# Validated BTC+ETH PF 1.54. Buy when RSI2 < 5 and Close > 200d SMA.
def cryptorsi(daily: pd.DataFrame, *, rsi_max: float = 5.0, sma_len: int = 200) -> dict | None:
    if len(daily) < sma_len:
        return None
    close = daily["close"]
    if _rsi2(close) < rsi_max and float(close.iloc[-1]) > _sma(close, sma_len):
        return {"name": "CRYPTORSI", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"RSI2<{rsi_max:.0f} oversold in uptrend"}
    return None


REGISTRY = {
    "MOONSHOT": moonshot,
    "CRYPTODIP": cryptodip,
    "CRYPTORSI": cryptorsi,
}
