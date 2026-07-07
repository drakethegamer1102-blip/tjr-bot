# Autonomous review changelog

Dated log of every change the improvement loop (or its supervising agent) ships.
One entry per run. Newest first.

## 2026-07-07 — CI fix + disable tjr

**Root cause found: the nightly auto-improve has crashed every night since it shipped.**
`scripts/review_bot.py` imports `python-dotenv`, which was never in `requirements.txt`.
Local venvs had it by accident; CI's fresh `pip install` didn't → `ModuleNotFoundError`
at 20:30 UTC daily (confirmed in Actions run history: a `failure` run every day at 16:30 ET).
Consequences until today: no nightly Telegram summaries, no auto-tuning, tjr never disabled.

**Changes:**
1. `requirements.txt`: added `python-dotenv>=1.0`; `review_bot.py` import is now
   fail-safe (try/except) since CI passes env vars directly.
2. `review_bot.py --apply` no longer rewrites `config.yaml` via `yaml.dump` (which
   destroyed all 72 comment lines — the tuning audit trail). New comment-preserving
   text patcher edits only the changed scalars, and refuses to write unless the
   patched text parses to exactly the dict-applied config.
3. `config.yaml`: **tjr disabled** per the ≥20-closed-trades + PF<0.9 rule:
   - Live 14d: 19 trades, 26% win, PF 0.59, −$1,257 (all of it from shorts: −$1,255).
   - All-time live: 22 trades, −$3,845. Today alone: AVGO short into a rally, −$472.
   - Long-only variant was considered and REJECTED: 60d backtest PF 0.38 (−$3,072)
     vs full tjr PF 0.85 — backtest contradicts live on direction, so no tune ships;
     the only protocol-clean action is disable.

**Gates:** pytest 62/62 in both the local venv and a fresh CI-equivalent venv.
`compare_strategies.py 60` baseline unchanged (it hardcodes its builds; disabling
tjr in config does not alter kept strategies' backtest PF: orb 1.06, vwap_rev 0).

**EVAL_SINCE:** left at 2026-06-15 — no live-strategy code changed, so momentum /
macd_trend / squeeze_breakout / vwap_rev history remains valid for the nightly loop.

**Research digest (5-agent web sweep, 33 findings):** SMC/ICT as a package has no
rigorous published backtest support; bleeding shorts into a rising tape is its
textbook failure mode. Best-evidenced candidates for a future strategy (dormant,
needs PF≥1.2 over ≥150 backtest trades to enable): (1) noise-band intraday momentum
with resting stop-entry orders (Zarattini/Aziz/Barbon — resting levels neutralize the
15-min IEX delay), (2) first-30-min → last-30-min momentum (Gao/Han/Li/Zhou),
(3) ORB gated by "stocks in play" relative volume. Recurring lessons: regime filters
earn their keep by REMOVING trades; daily-timeframe filters (SPY vs 200-day SMA,
daily ADX) are immune to the 15-min delay; 3% risk/trade is 3× the published norm;
paper fills overstate thin edges.
