# Autonomous improvement protocol

The scheduled review agent runs every other day after the close and follows THIS file
exactly. Goal: make the bot more profitable over weeks via evidence-gated changes —
**not** by chasing a target number, and **never** by weakening safety.

## Hard rules (never violate)
- **Paper only.** Never set `ALPACA_PAPER=false`. Never place or move real money.
- **Never loosen risk controls.** You may make them tighter, never looser. Specifically do NOT:
  raise `risk_per_trade` above 0.03, raise `max_position_pct` above 0.25, raise/disable
  `daily_max_loss_pct`, `daily_max_trades`, or `max_concurrent_positions`, or weaken the
  `_daily_halt` gate, the bracket stops, or the kill-switch.
- **Every change must pass two gates before `git push`:** (1) full `pytest` suite passes;
  (2) a backtest (`scripts/compare_strategies.py`) does not *worsen* the kept strategies'
  aggregate profit factor. If either fails → revert, push nothing.
- **No target-chasing.** Optimize profit factor, expectancy, and max drawdown. An 80%
  win-rate/return is not a goal (chasing it = overfitting).

## Data sufficiency (anti-overfitting)
- Do **not** judge or change a strategy on fewer than **20 closed trades**. Under 20 → report only.
- **Disable** a live strategy only if it has ≥20 closed trades AND profit factor < 0.9.
- **Enable** a dormant strategy (`momentum`, `rsi_pullback`, `orb`) only if a backtest over
  ≥60 days / ≥150 trades shows PF ≥ 1.2.
- **Tune** a parameter only with a backtest showing improvement, and change ONE thing per run.

## Each run
1. `git pull`.
2. Run `scripts/strategy_report.py` (live per-strategy results) and `scripts/compare_strategies.py 60` (backtests).
3. Identify what's working, what's losing, and anomalies.
4. Decide changes per the sufficiency rules — small and isolated.
5. `pytest` (must pass) + backtest (must not worsen). Good → `git push`; else revert.
6. Telegram a summary: what changed (or why nothing), per-strategy stats, equity/P&L.
7. Append a dated entry to `CHANGELOG_AUTO.md` with the change + reasoning.

## Priority work items
- **Over-shorting trending days** (caused the 2026-06-11 −6% day): DONE — regime_filter +
  market_filter shipped and enabled.
- ~~`submit_bracket` LIMIT/market mismatch~~ RESOLVED 2026-07-08: "market" entries are now
  marketable LIMITs capped `Broker.ENTRY_SLIPPAGE_CAP` (0.3%) through the signal price, so
  fills can't land far from the planned stop/target geometry (15-min IEX delay was letting
  stops sit 0.08-0.5% from actual fills).
- `noise_band` (dormant) enters at market on a delayed break instead of the published
  resting stop-entry design — convert to resting orders at precomputed levels before any
  re-enable, then require the PF>=1.2 backtest gate as usual.
- News gate (2026-07-08): fresh-headline symbols have RIPTIDE reversion entries blocked
  (`news_filter:` in config). Never widen it into an entry SIGNAL without backtest evidence.

## Escalate to the user (do NOT auto-do) — Telegram and stop:
Anything needing real-money mode, a paid data feed, or removing/loosening a safety rail.
