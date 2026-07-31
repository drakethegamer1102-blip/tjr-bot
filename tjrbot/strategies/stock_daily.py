"""Three DAILY stock strategies — validated on a 12-name basket over 15 years.

Like the futures-daily strategies, these are daily-bar decisions (one per day), which
sidesteps the intraday data problems that sank ORB/squeeze. All three are long-biased
mean-reversion / seasonal edges, validated on real daily data across every era
(2010-14 / 2015-19 / 2020-26) — not curve-fit. They trade Alpaca-tradable equities/ETFs
(SPY by default), so they can go live on the existing account. See STOCK_STRATEGY_RESEARCH.md.

  decide(daily) -> dict | None   # daily: DAILY bars oldest->newest, incl. today's bar
    {"name","side","entry_ref","exit","note"}
"""

from __future__ import annotations

import pandas as pd


def _sma(s: pd.Series, n: int) -> float:
    return float(s.iloc[-n:].mean()) if len(s) >= n else float("nan")


def _rsi2(close: pd.Series) -> float:
    """Connors RSI(2): a 2-period Wilder RSI, the classic short-term oversold gauge."""
    if len(close) < 4:
        return float("nan")
    delta = close.diff()
    up = delta.clip(lower=0)
    dn = (-delta).clip(lower=0)
    ru = up.ewm(alpha=0.5, adjust=False).mean()
    rd = dn.ewm(alpha=0.5, adjust=False).mean().replace(0, 1e-9)
    rs = ru / rd
    return float((100 - 100 / (1 + rs)).iloc[-1])


# ---- DIPSNAP: RSI(2) deeply oversold inside an uptrend (Connors) ----
# Validated PF 1.57 / 57% win; robust every era (1.84 / 1.47 / 1.51). The strongest of the
# three. Buy when RSI2 < 5 and price is above the 200-day SMA; exit next close.
def dipsnap(daily: pd.DataFrame, *, rsi_max: float = 5.0, sma_len: int = 200) -> dict | None:
    if len(daily) < sma_len:
        return None
    close = daily["close"]
    if _rsi2(close) < rsi_max and float(close.iloc[-1]) > _sma(close, sma_len):
        return {"name": "DIPSNAP", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"RSI2<{rsi_max:.0f} oversold in uptrend"}
    return None


# ---- PULLBACK: 10-day-low dip inside a golden-cross uptrend ----
# Validated PF 1.44 / 55% win; robust every era (1.57 / 1.26 / 1.55). Buy a fresh 10-day low
# only when the 50-day SMA is above the 200-day (confirmed trend). Exit next close.
def pullback(daily: pd.DataFrame, *, low_len: int = 10, fast: int = 50, slow: int = 200) -> dict | None:
    if len(daily) < slow:
        return None
    close = daily["close"]
    prior_low = float(daily["low"].iloc[-(low_len + 1):-1].min())
    if float(close.iloc[-1]) <= prior_low and _sma(close, fast) > _sma(close, slow):
        return {"name": "PULLBACK", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"{low_len}d-low dip in golden-cross uptrend"}
    return None


# ---- TUESDAY-EQ: Turnaround Tuesday on equities (Monday down -> long Tuesday) ----
# Validated PF 1.38 / 55% win; robust every era (1.49 / 1.61 / 1.14). Distinct calendar
# mechanism (16-20% overlap with the two dip strategies). Enter Tue open, exit Tue close.
def tuesday_eq(daily: pd.DataFrame) -> dict | None:
    if len(daily) < 2:
        return None
    last = daily.index[-1]
    if getattr(last, "weekday", None) is None or last.weekday() != 0:
        return None
    c = daily["close"].to_numpy()
    if c[-1] >= c[-2]:
        return None
    return {"name": "TUESDAY-EQ", "side": "long", "entry_ref": "next_open",
            "exit": "next_close", "note": "Turnaround Tuesday (Mon down)"}


REGISTRY = {
    "DIPSNAP": dipsnap,
    "PULLBACK": pullback,
    "TUESDAY-EQ": tuesday_eq,
}
