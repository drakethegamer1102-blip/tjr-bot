"""Three MORE futures-native DAILY strategies (v3 batch) — backtested on 26y of real ES.

Same interface + spirit as futures_daily.py / futures_daily_v2.py (both left untouched).
Each is a published mean-reversion edge, validated in THIS repo's harness on real ES=F daily
bars (yfinance, 2000-2026) with the next_open->next_close 1-day-hold fill model. Only edges
clearing PF>1.3 full-sample AND PF>1.15 on the 2021+ era with N>=20 were shipped, and all
three actually STRENGTHEN post-2021 (see scripts/validate_new_strategies.py). All long-biased.

  decide(daily) -> dict | None   # daily bars oldest->newest, incl. today's bar
    {"name","side","entry_ref","exit","note"}
"""

from __future__ import annotations

import pandas as pd


def _sma(s: pd.Series, n: int) -> float:
    return float(s.iloc[-n:].mean()) if len(s) >= n else float("nan")


# ---- RSI2: Connors 2-period RSI < 5 oversold in a 200d bull regime ----
# Backtest ES=F: N=153, 61% win, PF 1.53 (2021+ PF 2.68 — strongest recent edge), +$43.6k.
# A velocity oscillator distinct from REBOUND's raw 2-down-day streak; combines the DAYBREAK
# regime gate with an oversold pulse.
def rsi2(daily: pd.DataFrame, *, sma_n: int = 200, rsi_n: int = 2, rsi_max: float = 5.0) -> dict | None:
    if len(daily) < sma_n + 1:
        return None
    c = daily["close"]
    delta = c.diff()
    up = delta.clip(lower=0.0)
    dn = (-delta).clip(lower=0.0)
    ru = up.ewm(alpha=1.0 / rsi_n, adjust=False).mean()
    rd = dn.ewm(alpha=1.0 / rsi_n, adjust=False).mean().replace(0.0, 1e-9)
    rsi = 100.0 - 100.0 / (1.0 + ru / rd)
    if float(c.iloc[-1]) > _sma(c, sma_n) and float(rsi.iloc[-1]) < rsi_max:
        return {"name": "RSI2", "side": "long", "entry_ref": "next_open", "exit": "next_close",
                "note": f"RSI2={float(rsi.iloc[-1]):.0f}<{rsi_max:.0f} & close>{sma_n}d SMA"}
    return None


# ---- IBS: Internal Bar Strength — close in the bottom 20% of the day's range ----
# Backtest ES=F: N=1190, 57% win, PF 1.38 (2021+ PF 1.32), +$194.7k over 26y (deepest sample
# on the board). Single-bar geometry signal (close position in range) — needs no prior-day
# comparison, so fully orthogonal to REBOUND/GAPFILL/DAYBREAK. Filter-free per the published
# SPY edge.
def ibs(daily: pd.DataFrame, *, ibs_max: float = 0.2, sma_n: int = 0) -> dict | None:
    if len(daily) < max(sma_n + 1, 2):
        return None
    last = daily.iloc[-1]
    hi, lo, cl = float(last["high"]), float(last["low"]), float(last["close"])
    rng = hi - lo
    if rng <= 0:
        return None
    val = (cl - lo) / rng
    if val >= ibs_max:
        return None
    if sma_n > 0 and not (cl > _sma(daily["close"], sma_n)):
        return None
    return {"name": "IBS", "side": "long", "entry_ref": "next_open", "exit": "next_close",
            "note": f"IBS={val:.2f}<{ibs_max} weak-close mean reversion"}


# ---- BOLLREV: close below the lower 20d/2σ Bollinger Band, 200d bull regime ----
# Backtest ES=F: N=174, 57% win, PF 1.74 (2021+ PF 2.20 — strengthening), +$58.8k. A
# volatility-normalized oversold extension (σ-scaled), distinct from a fixed down-day count;
# the 200d filter is what makes the band edge profitable.
def bollrev(daily: pd.DataFrame, *, bb_n: int = 20, bb_k: float = 2.0, sma_n: int = 200) -> dict | None:
    if len(daily) < max(sma_n, bb_n) + 1:
        return None
    c = daily["close"]
    mid = _sma(c, bb_n)
    sd = float(c.rolling(bb_n).std(ddof=0).iloc[-1])
    lower = mid - bb_k * sd
    last_c = float(c.iloc[-1])
    if last_c > _sma(c, sma_n) and last_c < lower:
        return {"name": "BOLLREV", "side": "long", "entry_ref": "next_open", "exit": "next_close",
                "note": f"close<{bb_n}d-{bb_k}σ lower band & close>{sma_n}d SMA"}
    return None


REGISTRY = {
    "RSI2": rsi2,
    "IBS": ibs,
    "BOLLREV": bollrev,
}
