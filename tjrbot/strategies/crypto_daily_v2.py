"""Three MORE daily crypto strategies (v2 batch) — backtested on real BTC+ETH daily bars.

Same interface + spirit as crypto_daily.py (left untouched). Each was researched from a
published edge, then validated in THIS repo's harness on real yfinance BTC-USD (2014-2026)
+ ETH-USD data, combined, with the same next_open->next_close 1-day-hold fill model the
paper runner uses. Only edges clearing PF>1.3 full-sample AND PF>1.15 on the 2021+ era with
N>=20 were shipped (see scripts/validate_new_strategies.py). All long-biased.

  decide(daily) -> dict | None   # daily bars oldest->newest, incl. today's bar
    {"name","side","entry_ref","exit","note"}
"""

from __future__ import annotations

import pandas as pd


def _sma(s: pd.Series, n: int) -> float:
    return float(s.iloc[-n:].mean()) if len(s) >= n else float("nan")


# ---- BBREAK: Bollinger upper-band breakout (volatility-expansion momentum) ----
# Backtest BTC+ETH: N=604, 54% win, PF 1.53 (2021+ PF 1.52 — stable across eras), +$34.7k.
# Buy when close pushes above SMA20 + 2*std20 — a vol-scaled breakout that decouples from
# MOONSHOT's fixed 20d-high (fires in low-vol-then-expansion regimes MOONSHOT misses).
def bbreak(daily: pd.DataFrame, *, window: int = 20, k: float = 2.0) -> dict | None:
    close = daily["close"]
    if len(close) < window + 1:
        return None
    win = close.iloc[-window:]
    mid = float(win.mean())
    sd = float(win.std(ddof=0))
    upper = mid + k * sd
    c = float(close.iloc[-1])
    if sd > 0 and c > upper:
        return {"name": "BBREAK", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"close {c:.0f} > upper BB ({window},{k}σ)"}
    return None


# ---- TURNOFMONTH: long the turn-of-month window (last day + first 3 days of month) ----
# Backtest BTC+ETH: N=992, 56% win, PF 1.35 (2021+ PF 1.31), +$37.2k. Pure calendar edge
# (monthly-flow anomaly, McConnell-Xu / crypto ToM literature) — orthogonal to every
# price-based crypto strategy; fires ~4 days/month regardless of trend.
def turnofmonth(daily: pd.DataFrame, *, last_n: int = 1, first_n: int = 3) -> dict | None:
    ts = daily.index[-1]
    dom = ts.day
    days_in_month = pd.Period(ts, freq="M").days_in_month
    days_to_eom = days_in_month - dom
    if not ((days_to_eom < last_n) or (dom <= first_n)):
        return None
    return {"name": "TURNOFMONTH", "side": "long", "entry_ref": "next_open",
            "exit": "next_close", "note": f"turn-of-month (dom {dom}/{days_in_month})"}


# ---- WILLIAMSR: Williams %R(10) deeply oversold in a 200d uptrend (Larry Williams) ----
# Backtest BTC+ETH: N=149, 66% win, PF 1.44 (2021+ PF 1.26), +$8.9k. A raw range-position
# oscillator (distinct math from CRYPTORSI's RSI2) — buys close-near-range-low snapbacks
# only while Close > 200d SMA.
def williamsr(daily: pd.DataFrame, *, wr_len: int = 10, wr_thresh: float = -90.0,
              trend_len: int = 200) -> dict | None:
    c, h, l = daily["close"], daily["high"], daily["low"]
    if len(daily) < max(wr_len, trend_len) + 1:
        return None
    hh = float(h.rolling(wr_len).max().iloc[-1])
    ll = float(l.rolling(wr_len).min().iloc[-1])
    rng = hh - ll
    if rng == 0 or pd.isna(rng):
        return None
    willr = -100.0 * (hh - float(c.iloc[-1])) / rng
    st = _sma(c, trend_len)
    if pd.isna(st):
        return None
    if willr < wr_thresh and float(c.iloc[-1]) > st:
        return {"name": "WILLIAMSR", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"%R({wr_len})={willr:.0f} oversold, >200d SMA"}
    return None


REGISTRY = {
    "BBREAK": bbreak,
    "TURNOFMONTH": turnofmonth,
    "WILLIAMSR": williamsr,
}
