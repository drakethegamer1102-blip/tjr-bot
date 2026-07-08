# Autonomous review changelog

Dated log of every change the improvement loop (or its supervising agent) ships.
One entry per run. Newest first.

## 2026-07-08 — APEX + RIPTIDE: two virtual bots (user-directed build)

**Root-cause findings that shaped this:**
1. tjr deep-dive: sweep→MSS→FVG entries are inherently counter-trend (kept shorting
   rallies), and `plan_trade` forced `min_rr 3.0 × max(stop, 1.5%)` targets ≥4.5%
   away intraday — statistically unreachable on mega-caps → 5% win rate.
2. **The 3R-rewrite hurt EVERY strategy**: plan_trade discarded each strategy's own
   target (vwap_rev's VWAP target, band midlines) and rewrote it to 3R. Fixed via
   `honor_signal_target` in per-bot risk config.

**New architecture — two ensembles in one paper account, split by order-tag prefix:**
- **APEX** (`apx-`, trend/momentum): momentum, macd_trend, squeeze_breakout,
  **noise_band** (NEW — Zarattini-style time-of-day envelope break, VWAP-aligned;
  60d backtest PF 1.18, +$3,725 / 237 trades).
- **RIPTIDE** (`rip-`, mean reversion): vwap_rev (target now honored),
  **band_tag** (NEW — Keltner 2.5×ATR tag + RSI(2) + daily SMA10 trend gate;
  60d backtest PF 1.55, +$1,917 / 99 trades; PF 1.94 with regime filter),
  gap_fade (NEW but DORMANT — backtest PF 0.51/9t, needs PF≥1.2 to enable).
- Legacy `bot-` group retains the dormant strategies (tjr/orb/rsi_pullback/bollinger_rev).

**Learning phase (user directive: many trades, learn fast):** per-trade risk cut
3% → 1% (APEX) / 0.8% (RIPTIDE); per-bot envelopes 8/10 trades/day, 4 losses/day,
−2.5% realized daily loss each. UNCHANGED account rails: 5% daily halt, 3 concurrent
positions, 20% max position, brackets on every order, EOD flatten. Worst-case day is
still bounded at −5%; expected per-trade variance is 3-4× lower than before.

**Plumbing:** `bots:` config + per-strategy `bot:` assignment; per-bot coid prefixes;
`_bot_halts` per-bot daily gates; hist passed to NEEDS_HIST strategies; bars window
10d→16d (noise_band needs 14 sessions); IWM/DIA added for gap_fade; reports and
review_bot parse `apx-`/`rip-`; EVAL_SINCE → 2026-07-08.

**Gates:** pytest 73/73 (11 new tests); 60d backtest — kept strategies did not worsen
(orb 1.06→1.08, tjr n/a disabled). Anomaly logged: vwap_rev takes 0 backtest trades
(volume-confirmation gate too strict on backtest volume data) but trades live; monitor.

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
