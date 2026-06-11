# Graph Report - trading-bot  (2026-06-11)

## Corpus Check
- 41 files · ~13,320 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 256 nodes · 513 edges · 12 communities (9 shown, 3 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2bf24f30`
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

## God Nodes (most connected - your core abstractions)
1. `Broker` - 25 edges
2. `Journal` - 24 edges
3. `load_settings()` - 15 edges
4. `RiskConfig` - 15 edges
5. `plan_trade()` - 14 edges
6. `reconcile()` - 13 edges
7. `scan_once()` - 12 edges
8. `detect_structure()` - 12 edges
9. `Settings` - 11 edges
10. `Journal` - 11 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `Broker`  [EXTRACTED]
  scripts/scan_now.py → tjrbot/execution/alpaca_exec.py
- `main()` --calls--> `daily_summary()`  [EXTRACTED]
  scripts/run_bot.py → tjrbot/engine.py
- `test_summarize_trades()` --calls--> `summarize_trades()`  [EXTRACTED]
  tests/test_summary.py → tjrbot/engine.py
- `test_summarize_trades_empty()` --calls--> `summarize_trades()`  [EXTRACTED]
  tests/test_summary.py → tjrbot/engine.py
- `main()` --calls--> `Broker`  [EXTRACTED]
  scripts/run_bot.py → tjrbot/execution/alpaca_exec.py

## Import Cycles
- 1-file cycle: `tjrbot/dashboard/app.py -> tjrbot/dashboard/app.py`

## Communities (12 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (24): create_app(), A simple, readable dashboard: how the bot is doing, in plain English.  Reads you, Plain-English stats dashboard (Flask)., Flask, Row, Launch the stats dashboard at http://127.0.0.1:8787, _Broker, _Leg (+16 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (35): Series, Smart-Money-Concepts strategy engine., generate_signals(), Combine SMC primitives into TJR-style entry signals.  The TJR sequence (long exa, Signal, detect_structure(), find_swings(), Market-structure primitives for the TJR / Smart-Money-Concepts strategy.  These (+27 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (41): DataFrame, Journal, Notifications (Telegram phone alerts)., Telegram phone alerts via the Bot API (simple HTTP, no extra SDK)., Send a message. Returns True on success, False on any failure., TelegramNotifier, main(), Entry point for the trading bot.      python scripts/run_bot.py --dry-run --forc (+33 more)

### Community 3 - "Community 3"
Cohesion: 0.20
Nodes (9): Any, main(), Verify Alpaca + Telegram connectivity. Prints only non-secret status., load_env(), load_settings(), Path, Configuration: loads .env secrets and config.yaml settings., Minimal .env loader (KEY=VALUE per line). Does not overwrite real env vars. (+1 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (19): _clean(), get_crypto_bars(), get_stock_bars(), _parse_tf(), Historical / recent OHLCV bars from Alpaca, returned as a clean DataFrame.  Outp, Free Alpaca plans use the IEX feed and cannot read the most recent ~15 min., Market data access (Alpaca)., get_candidates() (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (26): DailyRiskState, plan_trade(), Position sizing, stop placement, and the daily kill-switch.  Your rule: a **10%, Tracks today's realised results so the kill-switch can halt trading., Return a reason string if trading should stop for the day, else None., Turn a raw signal into a sized, risk-checked trade plan (or None if invalid)., RiskConfig, TradePlan (+18 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (11): Broker, Alpaca paper-trading execution: bracket orders + account/position helpers.  A br, Recently closed orders, with bracket legs nested., True if Alpaca already has an order with this id (idempotency for stateless runs, True if the asset can be sold short (skip the trade otherwise)., Submit a limit entry with attached take-profit and stop-loss., A plain, non-marketable limit order — used only to verify the order path., Order execution (Alpaca paper trading). (+3 more)

### Community 7 - "Community 7"
Cohesion: 0.29
Nodes (6): 1. Make a scoped token for the timer (safe), 2. Create a free cron-job.org account, 3. Add 3 cron jobs, 4. Verify, Note on the old GitHub schedule, Reliable scheduling via cron-job.org (free, no credit card)

### Community 11 - "Community 11"
Cohesion: 0.47
Nodes (5): Tests for the summary aggregation (pure)., test_summarize_trades(), test_summarize_trades_empty(), Pure aggregation over [{'symbol','pnl','dt'}] rows (count, win rate, best/worst), summarize_trades()

## Knowledge Gaps
- **18 isolated node(s):** `1. Make a scoped token for the timer (safe)`, `2. Create a free cron-job.org account`, `3. Add 3 cron jobs`, `4. Verify`, `Note on the old GitHub schedule` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Broker` connect `Community 6` to `Community 0`, `Community 2`?**
  _High betweenness centrality (0.184) - this node is a cross-community bridge._
- **Why does `Journal` connect `Community 0` to `Community 2`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Why does `generate_signals()` connect `Community 1` to `Community 2`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Journal` (e.g. with `Journal` and `Settings`) actually correct?**
  _`Journal` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `1. Make a scoped token for the timer (safe)`, `2. Create a free cron-job.org account`, `3. Add 3 cron jobs` to the rest of the system?**
  _84 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.07474747474747474 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.11025641025641025 - nodes in this community are weakly interconnected._