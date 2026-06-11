# Graph Report - trading-bot  (2026-06-11)

## Corpus Check
- 50 files · ~16,139 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 308 nodes · 613 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ad2c1aa9`
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
- `test_reconcile_records_win_and_is_idempotent()` --calls--> `Journal`  [INFERRED]
  tests/test_reconcile.py → tjrbot/engine.py
- `test_reconcile_skips_open_positions()` --calls--> `Journal`  [INFERRED]
  tests/test_reconcile.py → tjrbot/engine.py
- `sig()` --calls--> `Signal`  [EXTRACTED]
  tests/test_risk.py → tjrbot/smc/signals.py
- `test_daily_loss_exceeded()` --calls--> `daily_loss_exceeded()`  [EXTRACTED]
  tests/test_risk.py → tjrbot/risk/engine.py
- `test_summarize_trades()` --calls--> `summarize_trades()`  [EXTRACTED]
  tests/test_summary.py → tjrbot/engine.py

## Import Cycles
- 1-file cycle: `tjrbot/strategies/__init__.py -> tjrbot/strategies/__init__.py`
- 1-file cycle: `tjrbot/dashboard/app.py -> tjrbot/dashboard/app.py`

## Communities (13 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (22): create_app(), A simple, readable dashboard: how the bot is doing, in plain English.  Reads you, Plain-English stats dashboard (Flask)., Flask, Row, Launch the stats dashboard at http://127.0.0.1:8787, _Broker, _Leg (+14 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (46): Signal, Smart-Money-Concepts strategy engine., in_session(), Trading session / ICT-style killzone time windows (US/Eastern)., True if timestamp `ts` (tz-aware or naive=UTC) falls in any named window., generate_signals(), Combine SMC primitives into TJR-style entry signals.  The TJR sequence (long exa, detect_structure() (+38 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (37): Journal, Notifications (Telegram phone alerts)., Telegram phone alerts via the Bot API (simple HTTP, no extra SDK)., Send a message. Returns True on success, False on any failure., TelegramNotifier, main(), Entry point for the trading bot.      python scripts/run_bot.py --dry-run --forc, main() (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.17
Nodes (11): Any, main(), Verify Alpaca + Telegram connectivity. Prints only non-secret status., main(), Safely verify the Alpaca order path: submit a non-marketable limit, then cancel, load_env(), load_settings(), Path (+3 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (21): _clean(), get_crypto_bars(), get_stock_bars(), _parse_tf(), Historical / recent OHLCV bars from Alpaca, returned as a clean DataFrame.  Outp, Free Alpaca plans use the IEX feed and cannot read the most recent ~15 min., Market data access (Alpaca)., get_candidates() (+13 more)

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
Nodes (34): Series, Signal, Non-SMC strategies that run alongside TJR (each returns tagged Signals).  Each s, generate(), Momentum / trend breakout.  In an up-trend (fast EMA above slow EMA), go long wh, generate(), Opening Range Breakout (ORB).  Long when a bar closes above the opening-range hi, generate() (+26 more)

### Community 12 - "Community 12"
Cohesion: 0.23
Nodes (13): RiskConfig, main(), Run a backtest and print a plain-English report.  Usage:     python scripts/back, main(), Backtest TJR vs ORB vs VWAP-reversion head-to-head on real data.  Same risk sett, backtest_strategy(), BacktestResult, DataFrame (+5 more)

## Knowledge Gaps
- **24 isolated node(s):** `DataFrame`, `DataFrame`, `Signal`, `DataFrame`, `Signal` (+19 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Broker` connect `Community 6` to `Community 0`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._
- **Why does `Journal` connect `Community 0` to `Community 2`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `generate_signals()` connect `Community 1` to `Community 11`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Journal` (e.g. with `Journal` and `Settings`) actually correct?**
  _`Journal` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Tests for position sizing, stop placement, and the daily kill-switch.`, `DataFrame`, `Live paper-trading engine: scan symbols -> size -> place bracket orders -> alert` to the rest of the system?**
  _103 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.07862679955703211 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07826694619147449 - nodes in this community are weakly interconnected._