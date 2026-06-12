"""Backtest TJR vs ORB vs VWAP-reversion head-to-head on real data.

Same risk settings for all (structural stop, 3% risk). Aggregates trades across
symbols; compares by win rate, profit factor, and expectancy — the metrics that
matter, not trade count. Usage: python scripts/compare_strategies.py [DAYS] [SYM,SYM,...]
"""

from __future__ import annotations

import sys

from tjrbot.backtest import backtest_strategy
from tjrbot.config import load_settings
from tjrbot.data.alpaca_data import get_stock_bars
from tjrbot.engine import _AGG
from tjrbot.risk.engine import RiskConfig
from tjrbot.strategies import orb, vwap_rev
from tjrbot.strategy import find_trades


def main(argv: list[str]) -> int:
    days = int(argv[1]) if len(argv) > 1 else 45
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

    builds = {
        "tjr (SMC)": tjr_build,
        "orb": lambda today, prev, hist: orb.generate(today, or_minutes=15, min_rr=rc.min_rr),
        "vwap_rev": lambda today, prev, hist: vwap_rev.generate(today, atr_mult=2.0),
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
        print(f"{name:11} {n:>6} {wr:>4.0f}% {f'{shorts}':>7} {pf_s:>6} ${exp:>8.0f} ${sum(t.pnl for t in trades):>9,.0f}")

    for use_regime in (False, True):
        label = "WITH regime filter" if use_regime else "WITHOUT regime filter (today's behavior)"
        print(f"\n=== {label} ===")
        print(f"{'strategy':11} {'trades':>6} {'win%':>5} {'shorts':>7} {'PF':>6} {'exp/trade':>10} {'totP&L':>10}")
        print("-" * 64)
        for name, build in builds.items():
            trades = []
            for sym, b in bars_by_sym.items():
                trades += backtest_strategy(b, sym, build, rc, use_regime=use_regime).trades
            row(name, trades)
    print("\n(Structural stop, 3% risk, 100k/symbol. Judge by PF + win%, not trade count.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
