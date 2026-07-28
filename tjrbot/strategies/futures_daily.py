"""Three futures-native DAILY strategies — validated on 26y of real ES futures data.

These are PRISTINE and SEPARATE from every other strategy in the bot. They operate on
DAILY bars (one decision per day), which suits a prop-firm account and sidesteps the
15-min-delayed intraday feed entirely. All three are long-biased (equity indices drift up)
and were each validated on real ES=F data over 2000-2026 AND re-checked on 2021+ (see
FUTURES_STRATEGY_RESEARCH.md). Nothing here is curve-fit; parameters are the round,
evidence-based defaults.

Each strategy exposes decide(daily) -> dict | None, where `daily` is a DataFrame of DAILY
bars (columns open/high/low/close, DatetimeIndex, oldest->newest, INCLUDING today's bar as
the last row). It returns a plan for the NEXT session, or None (no trade):
    {"name","side","entry_ref","exit","note"}
      entry_ref: "next_open" (enter at the next session's open)
      exit:      "next_close" (exit at that session's close) | "next_next_close"

Economics handled by the runner (ES=$50/pt, MES=$5/pt).
"""

from __future__ import annotations

import pandas as pd


def _sma(s: pd.Series, n: int) -> float:
    if len(s) < n:
        return float("nan")
    return float(s.iloc[-n:].mean())


# ---- DAYBREAK: long the day session only in a bull regime (Close > 200d SMA) ----
# Validated: 4642t, 57% win, PF 1.34 (2021+: PF 1.27). Below the 200d it LOSES (PF 0.85),
# so the regime filter IS the edge. Enter next open, exit next close.
def daybreak(daily: pd.DataFrame, *, sma_len: int = 200) -> dict | None:
    if len(daily) < sma_len:
        return None
    close = daily["close"]
    if float(close.iloc[-1]) > _sma(close, sma_len):
        return {"name": "DAYBREAK", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": f"bull regime (>{sma_len}d SMA)"}
    return None


# ---- REBOUND: buy after 2 consecutive DOWN days, hold 1 day (short-term reversal) ----
# Validated: 1293t, 57% win, PF 1.40 (2021+: PF 1.67 — strongest). Enter next open,
# exit the following close (hold ~1 day).
def rebound(daily: pd.DataFrame) -> dict | None:
    if len(daily) < 3:
        return None
    c = daily["close"].to_numpy()
    down_today = c[-1] < c[-2]
    down_prev = c[-2] < c[-3]
    if down_today and down_prev:
        return {"name": "REBOUND", "side": "long", "entry_ref": "next_open",
                "exit": "next_close", "note": "2 consecutive down days -> reversal"}
    return None


# ---- GAPFILL: fade a large overnight GAP-DOWN, exit same-day close ----
# Validated: 256t, 57% win, PF 1.35 (2021+: PF 1.68). When the NEXT session opens >0.3%
# below the prior close, buy that open and exit the same close — the gap tends to fill.
# Distinct from DAYBREAK (regime) and REBOUND (2-day hold): event-driven, same-day, active
# only ~4% of days. NOTE: this decides for the *upcoming* open using the last close; the
# runner confirms the gap once the open prints. (Originally considered a 50/200 trend filter
# "TIDERIDER" for the 3rd slot, but it agreed with DAYBREAK ~90% of the time — same bet
# twice — so it was replaced with this genuinely orthogonal edge.)
def gapfill(daily: pd.DataFrame, *, min_gap_pct: float = 0.003) -> dict | None:
    if len(daily) < 2:
        return None
    prev_close = float(daily["close"].iloc[-1])
    return {"name": "GAPFILL", "side": "long", "entry_ref": "next_open",
            "exit": "next_close", "note": f"fade gap-down > {min_gap_pct*100:.1f}%",
            "requires_gap_down_pct": min_gap_pct, "prev_close": prev_close}


REGISTRY = {
    "DAYBREAK": daybreak,
    "REBOUND": rebound,
    "GAPFILL": gapfill,
}
