# Graph Report - trading-bot  (2026-06-11)

## Corpus Check
- 52 files · ~16,889 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 319 nodes · 625 edges · 16 communities (12 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4bf49e0e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]

## God Nodes (most connected - your core abstractions)
1. `Broker` - 25 edges
2. `Journal` - 24 edges
3. `RiskConfig` - 15 edges
4. `load_settings()` - 15 edges
5. `scan_once()` - 14 edges
6. `plan_trade()` - 14 edges
7. `Settings` - 13 edges
8. `Journal` - 13 edges
9. `reconcile()` - 13 edges
10. `detect_structure()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `sig()` --calls--> `Signal`  [EXTRACTED]
  tests/test_risk.py → tjrbot/smc/signals.py
- `test_daily_loss_exceeded()` --calls--> `daily_loss_exceeded()`  [EXTRACTED]
  tests/test_risk.py → tjrbot/risk/engine.py
- `test_reconcile_records_win_and_is_idempotent()` --calls--> `Journal`  [INFERRED]
  tests/test_reconcile.py → tjrbot/engine.py
- `test_reconcile_skips_open_positions()` --calls--> `Journal`  [INFERRED]
  tests/test_reconcile.py → tjrbot/engine.py
- `test_summarize_trades()` --calls--> `summarize_trades()`  [EXTRACTED]
  tests/test_summary.py → tjrbot/engine.py

## Import Cycles
- 1-file cycle: `tjrbot/strategies/__init__.py -> tjrbot/strategies/__init__.py`
- 1-file cycle: `tjrbot/dashboard/app.py -> tjrbot/dashboard/app.py`

## Communities (16 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.20
Nodes (12): Signal, in_session(), Trading session / ICT-style killzone time windows (US/Eastern)., True if timestamp `ts` (tz-aware or naive=UTC) falls in any named window., make_bars(), Tests for the daily-bias and session filters., test_daily_bias_bullish(), test_session_filter() (+4 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (35): Smart-Money-Concepts strategy engine., generate_signals(), Combine SMC primitives into TJR-style entry signals.  The TJR sequence (long exa, Signal, detect_structure(), find_swings(), Market-structure primitives for the TJR / Smart-Money-Concepts strategy.  These, Return confirmed swing highs and lows using a symmetric fractal. (+27 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (49): Journal, Send a message. Returns True on success, False on any failure., TelegramNotifier, Row, main(), Entry point for the trading bot.      python scripts/run_bot.py --dry-run --forc, main(), Watch the bot scan the market right now (read-only — places no orders).  For eac (+41 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (19): Any, create_app(), A simple, readable dashboard: how the bot is doing, in plain English.  Reads you, Plain-English stats dashboard (Flask)., Flask, Launch the stats dashboard at http://127.0.0.1:8787, main(), Verify Alpaca + Telegram connectivity. Prints only non-secret status. (+11 more)

### Community 4 - "Community 4"
Cohesion: 0.24
Nodes (9): get_candidates(), rank_candidates(), Find tradable candidate stocks each scan ("go out and find stocks").  Pulls the, Pure filter+rank: keep ordinary stocks in the price band, sort by volume., Return up to `max_symbols` screened tickers, with `extra` (watchlist) kept first, Tests for the screener's filter/rank logic (pure, no API)., test_rank_filters_and_orders(), test_rank_respects_max_symbols() (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.16
Nodes (20): daily_loss_exceeded(), DailyRiskState, plan_trade(), Position sizing, stop placement, and the daily kill-switch.  Your rule: a **10%, Tracks today's realised results so the kill-switch can halt trading., Return a reason string if trading should stop for the day, else None., True if today's P&L (equity vs prior session close) is at/below -max_loss_pct., Turn a raw signal into a sized, risk-checked trade plan (or None if invalid). (+12 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (9): Broker, Alpaca paper-trading execution: bracket orders + account/position helpers.  A br, Recently closed orders, with bracket legs nested., True if Alpaca already has an order with this id (idempotency for stateless runs, True if the asset can be sold short (skip the trade otherwise)., Submit a limit entry with attached take-profit and stop-loss., A plain, non-marketable limit order — used only to verify the order path., Order execution (Alpaca paper trading). (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.29
Nodes (6): 1. Make a scoped token for the timer (safe), 2. Create a free cron-job.org account, 3. Add 3 cron jobs, 4. Verify, Note on the old GitHub schedule, Reliable scheduling via cron-job.org (free, no credit card)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (33): Series, Non-SMC strategies that run alongside TJR (each returns tagged Signals).  Each s, generate(), Momentum / trend breakout.  In an up-trend (fast EMA above slow EMA), go long wh, generate(), Opening Range Breakout (ORB).  Long when a bar closes above the opening-range hi, generate(), RSI pullback in the direction of the trend (Connors-style RSI(2)).  In an up-tre (+25 more)

### Community 12 - "Community 12"
Cohesion: 0.13
Nodes (23): _clean(), get_crypto_bars(), get_stock_bars(), _parse_tf(), Historical / recent OHLCV bars from Alpaca, returned as a clean DataFrame.  Outp, Free Alpaca plans use the IEX feed and cannot read the most recent ~15 min., Market data access (Alpaca)., RiskConfig (+15 more)

### Community 13 - "Community 13"
Cohesion: 0.29
Nodes (6): Autonomous improvement protocol, Data sufficiency (anti-overfitting), Each run, Escalate to the user (do NOT auto-do) — Telegram and stop:, Hard rules (never violate), Priority work items

### Community 14 - "Community 14"
Cohesion: 0.47
Nodes (5): Tests for the summary aggregation (pure)., test_summarize_trades(), test_summarize_trades_empty(), Pure aggregation over [{'symbol','pnl','dt'}] rows (count, win rate, best/worst), summarize_trades()

## Knowledge Gaps
- **29 isolated node(s):** `Hard rules (never violate)`, `Data sufficiency (anti-overfitting)`, `Each run`, `Priority work items`, `Escalate to the user (do NOT auto-do) — Telegram and stop:` (+24 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Broker` connect `Community 6` to `Community 2`, `Community 3`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Why does `Journal` connect `Community 2` to `Community 3`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `generate_signals()` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Journal` (e.g. with `Journal` and `Settings`) actually correct?**
  _`Journal` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Hard rules (never violate)`, `Data sufficiency (anti-overfitting)`, `Each run` to the rest of the system?**
  _109 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.11097560975609756 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.06335403726708075 - nodes in this community are weakly interconnected._