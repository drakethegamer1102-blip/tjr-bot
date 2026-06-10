# Graph Report - .  (2026-06-09)

## Corpus Check
- Corpus is ~12,352 words - fits in a single context window. You may not need a graph.

## Summary
- 242 nodes · 493 edges · 11 communities (9 shown, 2 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

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

## God Nodes (most connected - your core abstractions)
1. `Journal` - 25 edges
2. `Broker` - 22 edges
3. `load_settings()` - 15 edges
4. `RiskConfig` - 15 edges
5. `plan_trade()` - 14 edges
6. `reconcile()` - 13 edges
7. `scan_once()` - 12 edges
8. `detect_structure()` - 12 edges
9. `Settings` - 11 edges
10. `get_stock_bars()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `load_settings()`  [EXTRACTED]
  scripts/backtest.py → tjrbot/config.py
- `main()` --calls--> `Broker`  [EXTRACTED]
  scripts/run_bot.py → tjrbot/execution/alpaca_exec.py
- `main()` --calls--> `TelegramNotifier`  [EXTRACTED]
  scripts/run_bot.py → tjrbot/notify/telegram.py
- `main()` --calls--> `load_settings()`  [EXTRACTED]
  scripts/run_bot.py → tjrbot/config.py
- `main()` --calls--> `Journal`  [EXTRACTED]
  scripts/run_bot.py → tjrbot/journal.py

## Import Cycles
- 1-file cycle: `tjrbot/dashboard/app.py -> tjrbot/dashboard/app.py`

## Communities (11 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (22): create_app(), A simple, readable dashboard: how the bot is doing, in plain English.  Reads you, Plain-English stats dashboard (Flask)., Flask, Row, Launch the stats dashboard at http://127.0.0.1:8787, _Broker, _Leg (+14 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (36): Series, Smart-Money-Concepts strategy engine., generate_signals(), Combine SMC primitives into TJR-style entry signals.  The TJR sequence (long exa, Signal, detect_structure(), find_swings(), Market-structure primitives for the TJR / Smart-Money-Concepts strategy.  These (+28 more)

### Community 2 - "Community 2"
Cohesion: 0.14
Nodes (27): Journal, main(), Entry point for the trading bot.      python scripts/run_bot.py --dry-run --forc, Settings, Tests for the summary aggregation (pure)., test_summarize_trades(), test_summarize_trades_empty(), _closed_bot_trades() (+19 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (15): Any, Notifications (Telegram phone alerts)., Telegram phone alerts via the Bot API (simple HTTP, no extra SDK)., Send a message. Returns True on success, False on any failure., TelegramNotifier, main(), Verify Alpaca + Telegram connectivity. Prints only non-secret status., main() (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (21): _clean(), get_crypto_bars(), get_stock_bars(), _parse_tf(), Historical / recent OHLCV bars from Alpaca, returned as a clean DataFrame.  Outp, Free Alpaca plans use the IEX feed and cannot read the most recent ~15 min., Market data access (Alpaca)., RiskConfig (+13 more)

### Community 5 - "Community 5"
Cohesion: 0.19
Nodes (17): DailyRiskState, plan_trade(), Position sizing, stop placement, and the daily kill-switch.  Your rule: a **10%, Tracks today's realised results so the kill-switch can halt trading., Return a reason string if trading should stop for the day, else None., Turn a raw signal into a sized, risk-checked trade plan (or None if invalid)., RiskConfig, TradePlan (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.10
Nodes (8): Broker, Alpaca paper-trading execution: bracket orders + account/position helpers.  A br, Recently closed orders, with bracket legs nested., True if Alpaca already has an order with this id (idempotency for stateless runs, Submit a limit entry with attached take-profit and stop-loss., A plain, non-marketable limit order — used only to verify the order path., Order execution (Alpaca paper trading)., TimeInForce

### Community 7 - "Community 7"
Cohesion: 0.20
Nodes (12): Signal, in_session(), Trading session / ICT-style killzone time windows (US/Eastern)., True if timestamp `ts` (tz-aware or naive=UTC) falls in any named window., make_bars(), Tests for the daily-bias and session filters., test_daily_bias_bullish(), test_session_filter() (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.24
Nodes (9): get_candidates(), rank_candidates(), Find tradable candidate stocks each scan ("go out and find stocks").  Pulls the, Pure filter+rank: keep ordinary stocks in the price band, sort by volume., Return up to `max_symbols` screened tickers, with `extra` (watchlist) kept first, Tests for the screener's filter/rank logic (pure, no API)., test_rank_filters_and_orders(), test_rank_respects_max_symbols() (+1 more)

## Knowledge Gaps
- **11 isolated node(s):** `PreToolUse`, `DataFrame`, `RiskConfig`, `TimeFrame`, `DataFeed` (+6 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Broker` connect `Community 6` to `Community 0`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.184) - this node is a cross-community bridge._
- **Why does `Journal` connect `Community 0` to `Community 2`, `Community 4`?**
  _High betweenness centrality (0.164) - this node is a cross-community bridge._
- **Why does `generate_signals()` connect `Community 1` to `Community 7`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Journal` (e.g. with `Journal` and `Settings`) actually correct?**
  _`Journal` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PreToolUse`, `Run a backtest and print a plain-English report.  Usage:     python scripts/back`, `Launch the stats dashboard at http://127.0.0.1:8787` to the rest of the system?**
  _75 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.07862679955703211 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.10685249709639953 - nodes in this community are weakly interconnected._