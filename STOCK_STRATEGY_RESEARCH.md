# Stock strategy research — 3 new DAILY stock edges (validated 15y)

Built 2026-07-31. Three NEW daily stock strategies, validated on a 12-name basket
(AAPL/MSFT/NVDA/AMZN/META/GOOGL/JPM/XOM/JNJ/WMT/SPY/QQQ) over 15 years, profitable in
EVERY era (2010-14 / 2015-19 / 2020-26). Daily-bar design sidesteps the intraday data cap
that sank ORB/squeeze. All long-biased mean-reversion / seasonal. Alpaca-tradable (trade
SPY or a stock basket), so they can go live on the existing account.

## The 3 (kept)
| Name | Rule | Basket PF | Win% | Every era? |
|------|------|-----------|------|-----------|
| **DIPSNAP** | RSI(2) < 5 oversold AND Close > 200d SMA | 1.57 | 57% | ✅ 1.84/1.47/1.51 |
| **PULLBACK** | fresh 10-day low AND 50d SMA > 200d (golden) | 1.44 | 55% | ✅ 1.57/1.26/1.55 |
| **TUESDAY-EQ** | Turnaround Tuesday (Mon down → long Tue open→close) | 1.38 | 55% | ✅ 1.49/1.61/1.14 |

250-day SPY paper sim (100 sh): DIPSNAP +$3,808 (88% win), PULLBACK +$1,824, TUESDAY-EQ
+$1,495 — combined **+$7,126**.

## Distinctness
DIPSNAP & PULLBACK overlap ~66% on SPY (both "buy weakness in uptrend") but use different
triggers (RSI extreme vs 10-day low). TUESDAY-EQ is cleanly distinct (16-20% overlap).
Accepted: 3 real edges with some correlation beat forcing in a weak "distinct" loser.

## What did NOT pass (honest record)
- Any INTRADAY stock strategy (ORB, squeeze, breakouts) — no durable edge on 60-day data.
- Pure breakouts (Donchian/new-high) — failed era-robustness (died post-2000, as expected).
- Turn-of-month — only PF 1.10, too thin an edge to bother.

## Files
tjrbot/strategies/stock_daily.py · scripts/stock_daily_paper.py · tests/test_stock_daily.py
Ledger: stock_daily_ledger.json (repo root). Runs in the after-close digest; own Telegram
message (🟢 STOCK · DAILY). Paper only.
