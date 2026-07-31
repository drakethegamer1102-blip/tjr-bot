"""Three MORE futures-native DAILY strategies (v2 batch) — validated on 26y of real ES.

Same interface + spirit as futures_daily.py (which is left untouched): each is a daily-bar
decision, validated on real ES=F over 1999-2026 AND checked to be profitable in EVERY era
(1999-2007 / 2008-2015 / 2016-2020 / 2021-2026) — not just recent. Chosen to be DISTINCT in
mechanism from each other and from REBOUND (the existing star), so they diversify: at least
one tends to fire when the others are quiet. See FUTURES_STRATEGY_RESEARCH.md.

  decide(daily) -> dict | None   # daily: DAILY bars, oldest->newest, incl. today's bar
    {"name","side","entry_ref","exit","note"}
"""

from __future__ import annotations

import pandas as pd


def _sma(s: pd.Series, n: int) -> float:
    return float(s.iloc[-n:].mean()) if len(s) >= n else float("nan")


# ---- TUESDAY: Turnaround Tuesday — Monday down -> long Tuesday (day-of-week seasonal) ----
# Validated per-era PF: 1.12 / 1.41 / 2.58 / 1.29 (positive in ALL four eras). Distinct
# mechanism (calendar seasonality), only 19% trigger-overlap with REBOUND. Enter Tue open,
# exit Tue close.
def tuesday(daily: pd.DataFrame) -> dict | None:
    if len(daily) < 2:
        return None
    idx = daily.index
    # today's bar is Monday (weekday 0) and it closed down -> trade the NEXT session (Tue)
    last = idx[-1]
    if getattr(last, "weekday", None) is None:
        return None
    if last.weekday() != 0:                      # Monday only
        return None
    c = daily["close"].to_numpy()
    if c[-1] >= c[-2]:                            # Monday must be a down day
        return None
    return {"name": "TUESDAY", "side": "long", "entry_ref": "next_open",
            "exit": "next_close", "note": "Turnaround Tuesday (Mon down)"}


# ---- CAPITULATION: fade a big -1.5% panic day (single-day capitulation reversal) ----
# Validated per-era PF: 1.14 / 1.24 / 1.45 / 1.26 (all eras positive). A deeper, rarer
# signal than REBOUND's two small down days — catches sharp one-day flushes. ~19 trades/yr.
def capitulation(daily: pd.DataFrame, *, drop_pct: float = 0.015) -> dict | None:
    if len(daily) < 2:
        return None
    c = daily["close"].to_numpy()
    ret = (c[-1] - c[-2]) / c[-2]
    if ret <= -drop_pct:
        return {"name": "CAPITULATION", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"fade -{drop_pct*100:.1f}% panic day"}
    return None


# ---- DIPBUYER: buy a 10-day-low pullback inside a golden-cross uptrend ----
# A HIGH-QUALITY dip: only when price tags a 10-day low AND the 50d SMA is above the 200d
# (confirmed uptrend). Stricter/rarer than REBOUND's two-down-days, so the dips it buys are
# better-supported. Robust every era (2.78 / 1.09 / 1.76 / 1.50); on the recent 2y tracker
# sim it was 13t / 85% win / +$8.3k (MES x2). Fires ~11/yr. (Considered UPRIDE — a 2-up-day
# momentum edge — but it lost on the recent next-day-close path, so it was NOT shipped.)
def dipbuyer(daily: pd.DataFrame, *, low_len: int = 10, fast: int = 50, slow: int = 200) -> dict | None:
    if len(daily) < slow:
        return None
    low = daily["low"]
    close = daily["close"]
    prior_low = float(low.iloc[-(low_len + 1):-1].min())   # lowest low of the prior low_len days
    if float(close.iloc[-1]) <= prior_low and _sma(close, fast) > _sma(close, slow):
        return {"name": "DIPBUYER", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"{low_len}d-low pullback in golden-cross uptrend"}
    return None


REGISTRY = {
    "TUESDAY": tuesday,
    "CAPITULATION": capitulation,
    "DIPBUYER": dipbuyer,
}
