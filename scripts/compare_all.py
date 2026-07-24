"""Backtest EVERY strategy head-to-head on identical data/risk (full matrix).

Extends compare_strategies.py to also cover the APEX momentum family (momentum,
macd_trend, squeeze_breakout) that the original omits. Same engine, same symbols,
same risk config per bot. Usage: python scripts/compare_all.py [DAYS] [SYM,SYM,...]
"""

from __future__ import annotations

import copy as _copy
import sys

from tjrbot.backtest import backtest_strategy
from tjrbot.config import load_settings
from tjrbot.data.alpaca_data import get_stock_bars
from tjrbot.engine import _AGG
from tjrbot.risk.engine import RiskConfig
from tjrbot.strategies import (
    band_tag, confluence, gap_fade, macd_trend, momentum, noise_band, orb, squeeze_breakout, vwap_rev,
)
from tjrbot.strategy import find_trades


def main(argv: list[str]) -> int:
    days = int(argv[1]) if len(argv) > 1 else 60
    symbols = argv[2].split(",") if len(argv) > 2 else ["AAPL", "NVDA", "TSLA", "AMD", "MSFT", "SPY", "QQQ", "META"]
    s = load_settings()
    rc = RiskConfig.from_settings(s)
    st = s.strategy

    def tjr_build(today, prev, hist):
        pdh, pdl = float(prev["high"].max()), float(prev["low"].min())
        htf = hist.resample("1h").agg(_AGG).dropna()
        return find_trades(
            today, [pdh, pdl], htf_bars=htf if len(htf) >= 5 else None,
            pivot_strength=int(st.get("pivot_strength", 2)), fvg_atr_mult=float(st.get("fvg_atr_mult", 0.25)),
            atr_period=int(st.get("atr_period", 14)), confirm_window=int(st.get("confirm_window", 10)),
            min_rr=rc.min_rr, sessions=None, use_bias=True,
        )

    rc_apex = _copy.copy(rc); rc_apex.honor_signal_target = True; rc_apex.min_stop_pct = 0.008
    rc_rip = _copy.copy(rc); rc_rip.honor_signal_target = True; rc_rip.min_stop_pct = 0.004

    builds = {
        # APEX trend/momentum family
        "momentum": (lambda today, prev, hist: momentum.generate(today, adx_min=30), rc_apex),
        "macd_trend": (lambda today, prev, hist: macd_trend.generate(today, adx_min=20), rc_apex),
        "squeeze_breakout": (lambda today, prev, hist: squeeze_breakout.generate(today), rc_apex),
        "orb": (lambda today, prev, hist: orb.generate(today, or_minutes=15, min_rr=rc.min_rr), rc_apex),
        "noise_band": (lambda today, prev, hist: noise_band.generate(today, hist=hist), rc_apex),
        # RIPTIDE mean-reversion family
        "vwap_rev": (lambda today, prev, hist: vwap_rev.generate(today, atr_mult=2.5, min_bars_open=6), rc_rip),
        "band_tag": (lambda today, prev, hist: band_tag.generate(today, hist=hist), rc_rip),
        "confluence": (lambda today, prev, hist: confluence.generate(today, hist=hist), rc_rip),
        "gap_fade": (lambda today, prev, hist: gap_fade.generate(today, hist=hist), rc_rip),
        # legacy
        "tjr (SMC)": (tjr_build, rc),
    }

    bars_by_sym = {}
    for sym in symbols:
        b = get_stock_bars(s.alpaca_key, s.alpaca_secret, sym, "5Min", days)
        if not b.empty and len(b) > 50:
            bars_by_sym[sym] = b
    print(f"Data: {list(bars_by_sym)}  (~{days}d, 5Min, free IEX feed — indicative only)")

    def row(name, trades):
        n = len(trades)
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        gw, gl = sum(t.pnl for t in wins), -sum(t.pnl for t in losses)
        wr = (len(wins) / n * 100) if n else 0
        pf = (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0)
        pf_s = "inf" if pf == float("inf") else f"{pf:.2f}"
        exp = (sum(t.pnl for t in trades) / n) if n else 0
        shorts = sum(1 for t in trades if t.side == "short")
        print(f"{name:17} {n:>6} {wr:>4.0f}% {f'{shorts}':>7} {pf_s:>6} ${exp:>8.0f} ${sum(t.pnl for t in trades):>10,.0f}")

    for use_regime in (False, True):
        label = "WITH regime filter" if use_regime else "WITHOUT regime filter"
        print(f"\n=== {label} ===")
        print(f"{'strategy':17} {'trades':>6} {'win%':>5} {'shorts':>7} {'PF':>6} {'exp/trade':>10} {'totP&L':>11}")
        print("-" * 70)
        for name, (build, build_rc) in builds.items():
            trades = []
            for sym, b in bars_by_sym.items():
                trades += backtest_strategy(b, sym, build, build_rc, use_regime=use_regime).trades
            row(name, trades)
    print("\n(Structural stop, per-bot risk. Judge by PF + win% + sample size, not trade count alone.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
