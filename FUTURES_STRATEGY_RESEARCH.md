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

---

## Batch 2 (2026-07-31) — 3 MORE futures edges (all-era robust)

Added after the ORB-FUTURES intraday experiment proved a loser (−$5,485). Found via a
battery test of pre-specified published edges on 26y ES=F, keeping only those profitable in
ALL FOUR eras (1999-2007 / 2008-2015 / 2016-2020 / 2021-2026). Distinct in mechanism.

| Name | Rule | Per-era PF | 250d sim (MES×2) |
|------|------|-----------|------------------|
| **TUESDAY** | Turnaround Tuesday (Mon down → long Tue) | 1.12/1.41/2.58/1.29 | +$1,905 |
| **CAPITULATION** | fade a −1.5% panic day, exit next close | 1.14/1.24/1.45/1.26 | +$4,260 |
| **DIPBUYER** | 10-day-low dip in a golden-cross (50>200) uptrend | 2.78/1.09/1.76/1.50 | +$8,338 |

Combined all 6 futures-daily (DAYBREAK/REBOUND/GAPFILL + these): +$45,668 / 250d.

**Rejected (honest record):** UPRIDE (2-up-day momentum) passed the per-era PF screen but
LOST on the recent next-day-close path (−$1,775/250d) — not shipped. Pure breakouts
(50d/100d-high) failed era-robustness. Files: tjrbot/strategies/futures_daily_v2.py.
