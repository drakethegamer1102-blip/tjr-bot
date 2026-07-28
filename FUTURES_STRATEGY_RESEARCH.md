# Futures strategy research — validated on real ES futures (yfinance ES=F)

Built 2026-07-28. Purpose: 3 NEW futures-native strategies (prop-firm prep), separate
from every existing strategy. Only edges validated on REAL multi-year ES futures data
were kept — no curve-fitting, no proxy-only results.

## Why the earlier attempts failed
The first ORB-FUTURES rebuild and ~30 config variants all lost because they were tested
on **60 days of delayed IEX index-ETF proxies** — too short, wrong instrument, and one
early "+$9,915" result turned out to be a **timezone bug** (bars are UTC; a mislabeled
`between_time` entered at 11am not 3pm). Lesson logged: validate on real futures data over
years, and always sanity-check the clock.

## Data source (free, no key)
`yfinance` ticker **ES=F** (real E-mini S&P 500 futures):
- Daily: 6,527 bars back to 2000 (26 years).
- Hourly: ~13,700 bars over 2 years (intraday, incl. globex).

## The 3 validated edges (26yr + 2021+ robustness check)

| # | Name | Rule | Full 26yr | 2021+ | Kept? |
|---|------|------|-----------|-------|-------|
| A | **DAYBREAK** | Long the DAY session (buy ~open, sell ~close) ONLY when Close > 200-day SMA (bull regime) | 4642t, 57%, PF **1.34** | PF 1.27 | ✅ |
| C2 | **REBOUND** | Buy after 2 consecutive DOWN days, hold 1 day (short-term reversal) | 1293t, 57%, PF **1.40** | PF **1.67** | ✅ |
| G | **GAPFILL** | Buy the open when the session gaps DOWN >0.3% vs prior close; exit same-day close (gap fills) | 256t, 57%, PF **1.35** | PF **1.68** | ✅ |

Contrast that proves DAYBREAK's edge is regime-specific, not luck: the SAME intraday-long
BELOW the 200d SMA is PF 0.85 (loses -3345 pts). The edge is the regime filter.

**Distinctness check (why these 3, not others):** an earlier 3rd pick "TIDERIDER" (50d>200d
trend regime, PF 1.13) was DROPPED because it agreed with DAYBREAK ~90% of days over 26y —
effectively the same bet twice, which would double risk concentration on a prop account.
Replaced with GAPFILL, an event-driven same-day gap-fade active only ~4% of days. Pairwise
signal agreement of the final three: DAYBREAK/REBOUND 33%, DAYBREAK/GAPFILL 29%,
GAPFILL/REBOUND trigger-day overlap 31% — genuinely differentiated edges.

## What did NOT work (honest record — not shipped)
- Overnight hold (buy close, sell next open): PF 0.92 (folklore says positive; on ES over
  this period it loses — data beats folklore).
- Hourly first-bar intraday momentum: PF 0.99 (flat).
- ORB breakout, VWAP-fade, stretch-fade on index futures: all PF < 1.0 over 60d proxy.

## Notes for implementation
- These are DAILY-bar strategies (one decision per day), which suits a prop account far
  better than 5-min scalping and sidesteps the 15-min-delayed intraday feed entirely.
- Sizing/economics: ES = $50/point, MES (micro) = $5/point. Paper sim uses MES.
- All three are LONG-biased — consistent with equity indices' long-run upward drift; none
  rely on shorting, which also fits most prop risk rules.
