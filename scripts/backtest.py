"""Run a backtest and print a plain-English report.

Usage:
    python scripts/backtest.py [SYMBOL] [DAYS]
    python scripts/backtest.py AAPL 30
    python scripts/backtest.py BTC/USD 14
"""

from __future__ import annotations

import sys

from tjrbot.backtest import run_backtest, summarize
from tjrbot.config import load_settings
from tjrbot.data.alpaca_data import get_crypto_bars, get_stock_bars
from tjrbot.risk.engine import RiskConfig


def main(argv: list[str]) -> int:
    symbol = argv[1] if len(argv) > 1 else "AAPL"
    days = int(argv[2]) if len(argv) > 2 else 30

    s = load_settings()
    rc = RiskConfig.from_settings(s)
    tf = s.profile.get("timeframe", "5Min")

    if "/" in symbol:  # crypto
        bars = get_crypto_bars(s.alpaca_key, s.alpaca_secret, symbol, tf, days)
        sessions = ("ny", "london")
    else:  # stock
        bars = get_stock_bars(s.alpaca_key, s.alpaca_secret, symbol, tf, days)
        sessions = ("ny_open",)

    print(f"Fetched {len(bars)} {tf} bars for {symbol} (~{days} days).")
    if bars.empty:
        print("No data returned — try a different symbol or more days.")
        return 1

    res = run_backtest(bars, symbol, rc, timeframe=tf, sessions=sessions, strat=s.strategy)
    st = summarize(res)

    pf = st["profit_factor"]
    pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
    print(
        f"""
======== BACKTEST: {symbol} ({tf}, ~{days}d) ========
Sessions traded : {", ".join(sessions)}
Stop / risk     : {rc.stop_mode}  ({(rc.max_position_loss_pct or 0)*100:.0f}% stop, {rc.risk_per_trade*100:.0f}% account risk)

Trades          : {st['trades']}
  Win rate      : {st['win_rate']*100:.0f}%   ({st['wins']} wins / {st['losses']} losses)
  Exits         : {st['target_hits']} hit target | {st['stop_hits']} hit stop | {st['eod_exits']} closed end-of-day
Avg win         : ${st['avg_win']:,.0f}
Avg loss        : ${st['avg_loss']:,.0f}
Profit factor   : {pf_str}   (>1 = made money, <1 = lost money)
Expectancy      : ${st['expectancy']:,.0f} per trade
Total return    : {st['total_return']*100:+.1f}%   (${res.start_equity:,.0f} -> ${st['end_equity']:,.0f})
Max drawdown    : -{st['max_drawdown']*100:.1f}%
==================================================
NOTE: stock data is Alpaca's free IEX feed (thin) — results are indicative, not exact.
"""
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
