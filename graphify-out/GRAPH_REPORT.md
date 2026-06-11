# Graph Report - trading-bot  (2026-06-11)

## Corpus Check
- 48 files · ~15,344 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 293 nodes · 592 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ce959685`
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
3. `load_settings()` - 15 edges
4. `RiskConfig` - 15 edges
5. `plan_trade()` - 14 edges
6. `Journal` - 13 edges
7. `scan_once()` - 13 edges
8. `reconcile()` - 13 edges
9. `Settings` - 12 edges
10. `detect_structure()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `test_compute_pnl()` --calls--> `compute_pnl()`  [EXTRACTED]
  tests/test_reconcile.py → tjrbot/reconcile.py
- `test_reconcile_records_win_and_is_idempotent()` --calls--> `Journal`  [INFERRED]
  tests/test_reconcile.py → tjrbot/engine.py
- `test_reconcile_skips_open_positions()` --calls--> `Journal`  [INFERRED]
  tests/test_reconcile.py → tjrbot/engine.py
- `main()` --calls--> `backtest_strategy()`  [EXTRACTED]
  scripts/compare_strategies.py → tjrbot/backtest.py
- `test_rsi_uptrend_high()` --calls--> `rsi()`  [EXTRACTED]
  tests/test_indicators.py → tjrbot/indicators.py

## Import Cycles
- 1-file cycle: `tjrbot/dashboard/app.py -> tjrbot/dashboard/app.py`
- 1-file cycle: `tjrbot/strategies/__init__.py -> tjrbot/strategies/__init__.py`

## Communities (13 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (12): Row, _Broker, _Leg, _Order, Tests for trade reconciliation (closed bracket orders -> recorded win/loss)., test_compute_pnl(), test_reconcile_records_win_and_is_idempotent(), test_reconcile_skips_open_positions() (+4 more)

### Community 1 - "Community 1"
Cohesion: 0.12
Nodes (33): Smart-Money-Concepts strategy engine., generate_signals(), Combine SMC primitives into TJR-style entry signals.  The TJR sequence (long exa, detect_structure(), find_swings(), Market-structure primitives for the TJR / Smart-Money-Concepts strategy.  These, Return confirmed swing highs and lows using a symmetric fractal., Walk the bars chronologically and emit BOS / MSS events.      A swing found at i (+25 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (42): Journal, Notifications (Telegram phone alerts)., Telegram phone alerts via the Bot API (simple HTTP, no extra SDK)., Send a message. Returns True on success, False on any failure., TelegramNotifier, main(), Entry point for the trading bot.      python scripts/run_bot.py --dry-run --forc, main() (+34 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (16): Any, create_app(), A simple, readable dashboard: how the bot is doing, in plain English.  Reads you, Plain-English stats dashboard (Flask)., Flask, Launch the stats dashboard at http://127.0.0.1:8787, main(), Verify Alpaca + Telegram connectivity. Prints only non-secret status. (+8 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (19): _clean(), get_crypto_bars(), get_stock_bars(), _parse_tf(), Historical / recent OHLCV bars from Alpaca, returned as a clean DataFrame.  Outp, Free Alpaca plans use the IEX feed and cannot read the most recent ~15 min., Market data access (Alpaca)., get_candidates() (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (30): DailyRiskState, plan_trade(), Position sizing, stop placement, and the daily kill-switch.  Your rule: a **10%, Tracks today's realised results so the kill-switch can halt trading., Return a reason string if trading should stop for the day, else None., Turn a raw signal into a sized, risk-checked trade plan (or None if invalid)., RiskConfig, TradePlan (+22 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (9): Broker, Alpaca paper-trading execution: bracket orders + account/position helpers.  A br, Recently closed orders, with bracket legs nested., True if Alpaca already has an order with this id (idempotency for stateless runs, True if the asset can be sold short (skip the trade otherwise)., Submit a limit entry with attached take-profit and stop-loss., A plain, non-marketable limit order — used only to verify the order path., Order execution (Alpaca paper trading). (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.29
Nodes (6): 1. Make a scoped token for the timer (safe), 2. Create a free cron-job.org account, 3. Add 3 cron jobs, 4. Verify, Note on the old GitHub schedule, Reliable scheduling via cron-job.org (free, no credit card)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (26): Series, Signal, Non-SMC strategies that run alongside TJR (each returns tagged Signals).  Each s, generate(), Opening Range Breakout (ORB).  Long when a bar closes above the opening-range hi, generate(), VWAP mean-reversion.  Range-bound sessions (the majority) tend to revert to VWAP, Tests for the technical indicators. (+18 more)

### Community 12 - "Community 12"
Cohesion: 0.20
Nodes (13): Signal, in_session(), Trading session / ICT-style killzone time windows (US/Eastern)., True if timestamp `ts` (tz-aware or naive=UTC) falls in any named window., make_bars(), Tests for the daily-bias and session filters., test_daily_bias_bullish(), test_session_filter() (+5 more)

## Knowledge Gaps
- **20 isolated node(s):** `DataFrame`, `DataFrame`, `DataFrame`, `DataFrame`, `Signal` (+15 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Broker` connect `Community 6` to `Community 2`, `Community 3`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._
- **Why does `Journal` connect `Community 0` to `Community 2`, `Community 3`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Why does `generate_signals()` connect `Community 1` to `Community 11`, `Community 12`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Journal` (e.g. with `Journal` and `Settings`) actually correct?**
  _`Journal` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Backtest TJR vs ORB vs VWAP-reversion head-to-head on real data.  Same risk sett`, `Tests for the technical indicators.`, `Tests for trade reconciliation (closed bracket orders -> recorded win/loss).` to the rest of the system?**
  _95 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.1168091168091168 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.1166429587482219 - nodes in this community are weakly interconnected._