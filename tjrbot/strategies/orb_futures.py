"""Opening Range Breakout — FUTURES variant (ORB FUTURES).

Same fundamentals as the stock `orb` strategy (which is deliberately left UNTOUCHED):
a break of the first `or_minutes` opening range, confirmed by VWAP, one trade per
direction per day, stop on the opposite side of the range, `min_rr` target. This variant
adapts that logic for index futures (built for MES — the Micro E-mini S&P 500), which is
the natural instrument for a prop-firm account:

  * Prices are rounded to the contract TICK (MES = 0.25) so stops/targets sit on valid
    tradable prices, not fractional stock prices.
  * A minimum stop distance is expressed in TICKS (not a % of price), because a fixed
    percentage is meaningless on a futures point scale.
  * Signal carries `point_value` / `tick_size` so the execution + sizing layer can convert
    points to dollars ($5/point on MES) and size in whole contracts.

This is PAPER/simulation only for now (Alpaca has no futures; index-ETF bars stand in for
the MES price series during testing). It does not modify `orb.py` or any existing strategy.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import vwap
from ..smc.zones import atr
from ..smc.signals import Signal


# --- MES (Micro E-mini S&P 500) contract spec; override via config for other futures ---
MES_TICK_SIZE = 0.25      # minimum price increment
MES_POINT_VALUE = 5.0     # dollars per 1.00 index point per contract


def _round_to_tick(price: float, tick: float) -> float:
    return round(round(price / tick) * tick, 2)


def generate(
    today: pd.DataFrame,
    *,
    or_minutes: int = 15,
    min_rr: float = 2.0,
    atr_period: int = 14,
    max_or_atr: float = 4.0,
    vwap_confirm: bool = True,
    tick_size: float = MES_TICK_SIZE,
    point_value: float = MES_POINT_VALUE,
    min_stop_ticks: int = 8,
    **_,
) -> list[Signal]:
    """ORB signals adapted for an index-futures contract.

    Identical entry logic to the stock ORB (break of the opening-range high/low, confirmed
    by VWAP, one trade per direction per day). Differences, all futures-specific:
      * entry / stop / target are rounded to `tick_size` (valid tradable prices);
      * the stop is widened to at least `min_stop_ticks` ticks from entry (a futures-scale
        floor, replacing the stock version's % floor) so a stop never sits inside noise;
      * the Signal carries tick_size / point_value for the sizing + execution layer.
    """
    if len(today) < 4:
        return []

    start = today.index[0]
    or_end = start + pd.Timedelta(minutes=or_minutes)
    or_bars = today[today.index < or_end]
    n_or = len(or_bars)
    if n_or < 1 or n_or >= len(today):
        return []

    orh = float(or_bars["high"].max())   # opening-range high
    orl = float(or_bars["low"].min())    # opening-range low

    vw = vwap(today).to_numpy()
    a = atr(today, atr_period).to_numpy()
    closes = today["close"].to_numpy()

    # Skip abnormally wide opening ranges (stops/targets would be enormous).
    if a[n_or - 1] > 0 and (orh - orl) > max_or_atr * a[n_or - 1]:
        return []

    min_stop = min_stop_ticks * tick_size

    out: list[Signal] = []
    fired_long = fired_short = False
    for i in range(n_or, len(today)):
        c = float(closes[i])
        v = float(vw[i])
        if not fired_long and c > orh and (not vwap_confirm or c > v):
            entry = _round_to_tick(c, tick_size)
            stop = min(orl, entry - min_stop)          # opposite side of range, floored
            stop = _round_to_tick(stop, tick_size)
            risk = entry - stop
            if risk > 0:
                target = _round_to_tick(entry + min_rr * risk, tick_size)
                out.append(Signal(i, "long", entry, stop, target,
                                  [f"break>{orh:.2f}", "above VWAP", "MES"],
                                  strategy="orb_futures", entry_type="market"))
                fired_long = True
        elif not fired_short and c < orl and (not vwap_confirm or c < v):
            entry = _round_to_tick(c, tick_size)
            stop = max(orh, entry + min_stop)          # opposite side of range, floored
            stop = _round_to_tick(stop, tick_size)
            risk = stop - entry
            if risk > 0:
                target = _round_to_tick(entry - min_rr * risk, tick_size)
                out.append(Signal(i, "short", entry, stop, target,
                                  [f"break<{orl:.2f}", "below VWAP", "MES"],
                                  strategy="orb_futures", entry_type="market"))
                fired_short = True
        if fired_long and fired_short:
            break
    return out


def contracts_for(account_equity: float, entry: float, stop: float,
                 *, point_value: float = MES_POINT_VALUE,
                 risk_fraction: float = 0.01, max_contracts: int = 10) -> int:
    """Whole-contract size so a stop-out risks ~risk_fraction of the account.

    dollar risk per contract = |entry - stop| (points) * point_value ($/point).
    """
    risk_points = abs(entry - stop)
    if risk_points <= 0:
        return 0
    dollar_risk_per_contract = risk_points * point_value
    n = int((account_equity * risk_fraction) / dollar_risk_per_contract)
    return max(0, min(n, max_contracts))
