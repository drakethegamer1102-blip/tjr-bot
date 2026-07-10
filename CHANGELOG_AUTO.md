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

## 2026-07-08 — review-bot anti-overfit gate fixed (MIN_TRADES 5 → 20)

**Anomaly found:** last night's CI auto-review (a7f63f8) disabled `noise_band` after a
single 0-for-5 day (−$1,013). Protocol forbids judging any strategy on <20 closed
trades, but `review_bot.py` had `MIN_TRADES = 5` — the nightly loop was allowed to
overreact to one bad day.

**Change (one per run):** `scripts/review_bot.py` `MIN_TRADES` 5 → 20, matching the
protocol. Pure tightening: the auto-tuner now needs 4× more evidence before it
disables, re-enables, or tunes anything. No strategy code touched.

**noise_band left OFF despite the rule-violating disable:** re-enabling requires a
backtest PF ≥ 1.2, and today's 60d backtest shows PF 1.13 / 243 trades — close but
below the bar. It stays dormant; future runs re-evaluate. Its 5 live trades remain
in the ledger and count toward the 20-trade sample if re-enabled later.

**Live snapshot (since EVAL_SINCE 2026-06-15):** equity $90,204, today −$1,156
(−$1,013 of it noise_band's debut). momentum 14t PF 0.72, macd_trend 1t,
squeeze_breakout 2t 2/2, tjr 15t PF 0.00 (already disabled 07-07), noise_band 5t 0/5.
Every live strategy is under 20 trades in-window → no strategy judgments this run.

**Backtest (60d, unchanged by this run):** band_tag PF 1.94 with regime filter (best),
noise_band 1.13, orb 1.03, tjr 0.84, gap_fade 0.51. Regime filter continues to earn
its keep (band_tag 1.51 → 1.94 with filter on).

**Gates:** pytest 73/73 passed. Backtest baseline identical (no strategy code changed).
**EVAL_SINCE:** unchanged — review infra only, live strategy history remains valid.

## 2026-07-08 (evening, user-directed) — trade-ledger bug hunt + news layer

Reviewed all 37 closed round-trips order-by-order. Three defects found, two fixed:

1. **Anti-stacking guard blind to the new bots** (`Broker.has_open_order`): it only
   matched `bot-`/`tjr-` order ids, so pending `apx-`/`rip-` entries were invisible
   and a later scan could stack a second bracket on the same symbol. Fixed with a
   shared `BOT_ORDER_PREFIXES` tuple.
2. **Market entries inherited stale-price geometry**: stops/targets are computed off
   the signal bar (15-min delayed IEX), but the MARKET entry filled at the live
   price — ledger showed stops filling 0.08–0.5% from entry despite the 1.5% floor
   (MSFT 06-23 stopped the minute it entered; AAPL 07-01 stopped 0.54% below fill).
   "market" entries are now marketable LIMITs capped 0.3% through the signal price:
   fill near the plan or don't fill at all (no trade = no risk). EVAL_SINCE → 2026-07-09.
3. **Account-level daily trade/loss counters don't see apx-/rip- orders** — reviewed
   with the user, kept AS DESIGNED for the learning phase (per-bot envelopes + the
   prefix-independent 5% equity halt govern the bots) and documented in code.

**News layer (user directive "go off the news every morning")**: new `tjrbot/news.py`
(Alpaca/Benzinga, free with existing keys, fail-open). Engine gate drops RIPTIDE
reversion signals on symbols with a headline in the last 18h (`news_filter:` config) —
news moves trend; fading them is how reversion gets run over. New
`scripts/morning_brief.py` + CI mode `morning-brief` sends a pre-open Telegram digest
(needs a cron-job.org entry ~9:00 ET weekdays, mode=morning-brief).

**Gates:** pytest 86/86 (13 new tests in tests/test_execution_and_news.py);
compare_strategies 60 unchanged (band_tag 1.94 / noise_band 1.13 / orb 1.03 with filter).

## 2026-07-09 (user-directed) — second bug sweep: 4 found, 4 fixed

1. **vwap_rev could never fire** (the big one): the 06-12 EMA-alignment filter
   contradicted its own stretch condition — price >2.5 ATR above VWAP is virtually
   never below EMA20 on the same bar. 60d backtest: ZERO trades while "enabled".
   Removed the gate; counter-trend protection stays with the engine's ADX regime
   filter + market-breadth filter (built after that gate, for exactly that job).
   Variant sweep: no-EMA = 31 trades / 55% win / PF 2.18 / +$1,237 over 60d
   (stricter-RSI and 3-ATR variants worse or dead — the EMA gate was the defect,
   not looseness). Rewrote the two EMA-gate unit tests: one now covers the plain
   oversold-stretch long, the other proves regime.filter_signals blocks the
   counter-trend short the removed gate used to.
2. **reconcile.py missed legacy trades**: its prefix tuple lacked "tjr-", so
   pre-multi-strategy round-trips never reached the journal. Root cause was three
   hand-rolled copies of the prefix list — now ONE canonical `BOT_PREFIXES` in
   config.py, imported by engine, execution, and reconcile.
3. **News fetch could silently truncate**: Alpaca caps a page at 50 stories; a busy
   18h window over ~29 symbols overflows that, and missing symbols read as "no
   news" (gate fails open). fetch_headlines now follows next_page_token (max 4
   pages / 200 stories). Live check: 68 headlines across the watchlist.
4. Stale regime.py docstring said the filter is "off by default" — it has been on
   since 06-12.

**Gates:** pytest 86/86. Backtest: vwap_rev 0 trades -> PF 2.18/31t; all other
strategies unchanged (orb/noise_band moved ±0.01-0.06 purely from the 60d window
sliding a day). EVAL_SINCE already 2026-07-09, covers the vwap_rev change.
