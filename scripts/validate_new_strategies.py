#!/usr/bin/env python3
"""Backtest harness for CANDIDATE daily strategies before they're added to the bot.

Pulls max-available daily history (yfinance) for crypto (BTC/ETH) or ES futures, runs any
decide(daily)->dict|None function over the FULL history with the same next_open->next_close
(or next_next_close) fill model the paper runners use, and reports N / win% / PF / expectancy
over the full sample AND the 2021+ era. Only strategies that clear the bar (PF>1.3, adequate
N, and hold up post-2021) should be promoted into tjrbot/strategies/*.

Usage:
    python scripts/validate_new_strategies.py crypto   # runs CANDIDATES_CRYPTO on BTC+ETH
    python scripts/validate_new_strategies.py futures   # runs CANDIDATES_FUTURES on ES=F

Edit the CANDIDATES_* dicts below to point at the functions under test.
"""
from __future__ import annotations

import sys
from datetime import datetime

import pandas as pd


def fetch(ticker: str, period: str = "max") -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()


def simulate(decide, daily: pd.DataFrame, point_value: float = 1.0, notional: float | None = None):
    """Walk history; on each qualifying day, enter next open, exit per plan. Returns trade pnls.

    point_value: $ per point (ES=50). notional: fixed-$ position (crypto=10000). Exactly one.
    """
    trades = []
    idx = daily.index
    for t in range(len(daily) - 2):  # need next (and possibly next-next) bar
        window = daily.iloc[: t + 1]
        try:
            plan = decide(window)
        except Exception:
            continue
        if not plan:
            continue
        # GAPFILL-style gate: only take if the next open actually gapped down enough
        gap_req = plan.get("requires_gap_down_pct")
        nxt = daily.iloc[t + 1]
        entry = float(nxt["open"])
        if gap_req is not None:
            prev_close = float(plan.get("prev_close", daily["close"].iloc[t]))
            if not (entry <= prev_close * (1 - gap_req)):
                continue
        exit_kind = plan.get("exit", "next_close")
        if exit_kind == "next_next_close":
            if t + 2 >= len(daily):
                continue
            exit_ = float(daily.iloc[t + 2]["close"])
        else:
            exit_ = float(nxt["close"])
        if notional is not None:
            units = notional / entry
            pnl = (exit_ - entry) * units
        else:
            pnl = (exit_ - entry) * point_value
        trades.append({"day": str(idx[t + 1].date()), "pnl": pnl})
    return trades


def stats(trades: list[dict]) -> dict:
    n = len(trades)
    if not n:
        return {"n": 0, "win": 0, "pf": 0, "exp": 0, "net": 0}
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gp, gl = sum(wins), abs(sum(losses))
    pf = (gp / gl) if gl else float("inf")
    return {"n": n, "win": 100 * len(wins) / n, "pf": pf,
            "exp": sum(pnls) / n, "net": sum(pnls)}


def era_report(name: str, trades: list[dict]):
    full = stats(trades)
    recent = stats([t for t in trades if t["day"] >= "2021-01-01"])
    def fmt(s):
        pf = "inf" if s["pf"] == float("inf") else f"{s['pf']:.2f}"
        return f"N={s['n']:4d} win={s['win']:4.0f}% PF={pf:>5s} exp=${s['exp']:+.1f} net=${s['net']:+,.0f}"
    verdict = "✅ PASS" if (full["pf"] > 1.3 and recent["pf"] > 1.15 and full["n"] >= 20) else "❌ below bar"
    print(f"  {name:14s} FULL  {fmt(full)}")
    print(f"  {'':14s} 2021+ {fmt(recent)}   {verdict}")


# ── Candidate registries — filled in once the research agents return specs ──
# Each entry: "NAME": decide_function
CANDIDATES_CRYPTO: dict = {}
CANDIDATES_FUTURES: dict = {}


def main(argv):
    which = argv[1] if len(argv) > 1 else "crypto"
    print(f"=== validate {which} · {datetime.now():%Y-%m-%d %H:%M} ===")
    if which == "crypto":
        if not CANDIDATES_CRYPTO:
            print("No crypto candidates wired in yet."); return 0
        for coin, tk in {"BTC": "BTC-USD", "ETH": "ETH-USD"}.items():
            daily = fetch(tk)
            print(f"\n{coin} ({tk}) — {len(daily)} bars {daily.index[0].date()}..{daily.index[-1].date()}")
            for name, fn in CANDIDATES_CRYPTO.items():
                era_report(name, simulate(fn, daily, notional=10_000.0))
    else:
        daily = fetch("ES=F")
        print(f"\nES=F — {len(daily)} bars {daily.index[0].date()}..{daily.index[-1].date()}")
        for name, fn in CANDIDATES_FUTURES.items():
            era_report(name, simulate(fn, daily, point_value=50.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
