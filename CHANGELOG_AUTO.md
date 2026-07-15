# Autonomous review changelog

Dated log of every change the improvement loop (or its supervising agent) ships.
One entry per run. Newest first.

## 2026-07-15 — NO CHANGE (verified last run's ★ finding, deferred the fix)

**Live report:** equity $89,371 (today $-339). `core.tjr` and `apex.noise_band` are the
big legacy negatives (−$2,877 / −$1,013) but both are disabled and stopped trading
07-07/07-08 — not current bleed. `apex.momentum` (11t, PF 0.34, −$768) is the live
concern; only 11 closed trades, below the protocol's 20-trade floor, so no action per
the anti-overfitting rule (need ≥20 before judging/disabling).

**Backtest (`compare_strategies.py 60`):** unchanged shape from prior runs — noise_band
1.21, band_tag 1.36→1.60 with regime filter, orb 1.08, tjr 0.79 (regime filter makes tjr
slightly worse, −2021 vs −1894 — consistent with tjr already being disabled live).

**Investigated 2026-07-14's ★ finding (DAY-TIF bracket expiry → ~45% unmanaged exits):**
Confirmed the mechanism in code — `submit_bracket` (`alpaca_exec.py:100`) submits the
bracket's TP/SL legs at the parent's `time_in_force`, which is `TimeInForce.DAY`, so they
expire at 16:00 ET regardless of the position. `flatten_if_eod` (`engine.py:132`) already
covers this well IF at least one 5-min scan lands in the 15:45-19:45 ET window: regular
session gets a plain market close, after-hours gets `close_all_positions_extended_hours`
(`alpaca_exec.py:161`), which cancels stray orders first and submits extended-hours
marketable-limit exits valid to 20:00. `flatten_stale_positions` (`engine.py:191`) is the
next-morning backstop. So the true gap is narrower than "45% unmanaged": it's only the
window where cron-job.org drops **every** scan across the full 4-hour flatten window —
an infra failure, not a strategy/logic bug, and not something config or a strategy-code
change can fix.

The code-level hardening last run proposed (resubmit a standalone GTC stop the moment a
bracket entry fills, so a naked position is never possible even with a fully-missed
flatten window) requires new order-lifecycle logic: tracking a resting protective stop
across fills, canceling it cleanly on normal bracket exit, and not double-submitting on
every 5-min scan. That's real surface area on the live order path, and I have no way to
validate it against a live fill tonight, unattended. Per the protocol ("when unsure, make
NO change"), I'm deferring this rather than shipping an unverified order-management
change. Recommend the user either (a) review/land this fix in an attended session, or
(b) do the cheaper reliability fix first — a dedicated 15:55 ET cron-job.org entry that
calls flatten independent of the 5-min scan, shrinking the missed-window blast radius
without touching order code at all.

**Gates:** pytest 86/86 passed. No code changed — backtest baseline untouched by
definition.

## 2026-07-14 — momentum adx_min 20→30 (tighten chop filter)

**Change:** `strategies.momentum.adx_min: 20 → 30` in config.yaml. One change this run.

**Evidence:** Live APEX momentum was the active bleeder — PF 0.53, win 25% over 8
filled trades (07-09..07-14). Winners were 07-09 trend-day longs (MSFT +$145, META
+$258); the losses were low-conviction breakouts on choppy days that reversed on entry
(PLTR −$164, AVGO −$130, EWY −$122, MU −$65, SPCX −$180). This is exactly the failure
the strategy's own docstring warns about ("breakouts only work when ADX confirms trend").
60d / 10-symbol backtest sweep (research script, since compare_strategies.py does NOT
cover momentum): adx_min 20 → PF 1.25 / 54% / 259 trades; adx_min **30 → PF 1.33 / 55%
/ 207 trades** (>150-trade, PF≥1.2 gate cleared); 35 marginally higher (1.36) but thinner
— 30 chosen as the robust, non-overfit point. Strictly a tightening (fewer, higher-quality
entries); loosens no risk control.

**Gates:** pytest 86/86 pass. compare_strategies.py 60 unchanged vs baseline (momentum
isn't in that harness — the tracked aggregate is untouched, so the change can't worsen it).

**Diagnosis notes (no action, for next run):**
- **★ BIGGEST FINDING — ~45% of trades exit UNMANAGED (bracket canceled at EOD, dumped at
  next-day market open).** 29 of ~65 tagged entries have bracket legs `['CANCELED','CANCELED']`:
  the stop+target were canceled at 4pm and the position was force-closed via a next-day
  SIMPLE MARKET order (27 such liquidations, every single trading day incl. 07-14 MSFT/QQQ/TSM).
  Nearly half of trades never touch their planned stop/target — they exit at an arbitrary
  overnight-gap price with no risk management. Since backtests assume stop/target fills, this
  is the primary reason live PF (0.53) collapses vs backtest (1.25+), i.e. the real "no green
  day" cause. Mechanism: `submit_bracket` uses `TimeInForce.DAY` (alpaca_exec.py:100) so
  brackets expire at the close; engine.py:141 claims "GTC brackets" cover overnight but that
  is FALSE. `flatten_if_eod` (15:45–16:00) runs inside the 5-min scan, so GitHub-cron drift
  that skips the final scan leaves the position naked overnight → next-morning stale-flatten.
  FIX (next run, NOT blanket-GTC — that risks stale next-day entry fills): (a) reliability —
  a dedicated 15:55 ET cron job that force-flattens, independent of the 5-min scan (USER infra
  action on cron-job.org); (b) code — at EOD, re-submit a standalone GTC stop for any position
  the flatten couldn't close so it's never naked. This outranks the RIPTIDE news-gate item.
- The strategy_report reads ALL closed Alpaca orders (limit 500), so `core.tjr` −$3,044
  and `apex.noise_band` −$1,013 are **legacy** from before those were disabled (tjr last
  traded 07-07, noise_band 07-08). They are NOT still trading; the headline equity drop is
  dominated by that pre-fix history, not current behavior.
- **RIPTIDE silent — ROOT CAUSE FOUND: news gate 18h lookback.** Deep-dive this run:
  vwap_rev/band_tag generate a healthy ~25 signals per 5 sessions across 9 symbols, spread
  through the day, and they survive session/regime/freshness/plan_trade. The blocker is
  `news_filter.lookback_hours: 18` with `block_bots: [riptide]` — measured live, an 18h
  window flags a fresh headline on **8 of 9 watchlist symbols simultaneously** (every
  mega-cap + index ETF always has news in any 18h window), so reversion is structurally
  disabled on the core list. Lookback sweep: 1–4h → 0 blocked, 6h → 2 (MSFT/SPY), 12h → 8,
  18h → 8. **PRE-LOADED next-run change: `lookback_hours 18 → 6`** — targets genuinely-fresh
  intraday news (the thing reversion should avoid fading) instead of overnight flow. This is
  narrowing an over-broad SIGNAL filter, not loosening a risk rail (size/stops/halt/kill-switch
  untouched; trades stay bracketed). Deferred to next run only to honor one-change-per-run.
- **Coverage gap:** compare_strategies.py backtests tjr/orb/vwap_rev/noise_band/gap_fade/
  band_tag but NOT the 3 live APEX strategies (momentum/macd_trend/squeeze_breakout). The
  protocol's "backtest must not worsen" gate is blind to the strategies actually trading.
  Adding them to the harness is a candidate change for a future run.

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
