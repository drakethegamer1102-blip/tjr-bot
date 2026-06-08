# TJR / SMC Trading Bot

An automated trading bot that scans the market for Smart-Money-Concepts (SMC)
setups in the style of TJR, manages risk, executes on **Alpaca paper trading**,
sends phone alerts via **Telegram**, and shows a plain-English stats dashboard.

> ⚠️ Paper trading only for now (fake money, real data). No bot can guarantee
> profits — see `PROJECT_PLAN.md` for the honest version.

## Read first
- **`PROJECT_PLAN.md`** — the full plan, the strategy spec, risk rules, and what
  you need to connect. Start there.

## Layout
```
tjrbot/
  smc/            strategy engine (sweep -> MSS/BOS -> FVG/OB -> signal)
    structure.py  swing pivots, Break of Structure (BOS), Market Structure Shift (MSS)
    zones.py      fair value gaps (FVG), order blocks, liquidity sweeps, ATR
    signals.py    combines the above into TJR-style entry signals
tests/            unit tests proving the engine fires correctly
config.yaml       all tunable settings (markets, risk, strategy params)
.env.example      template for your secret keys (copy to .env)
```

## Setup
```bash
/Users/drake/.local/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env        # then fill in your Alpaca + Telegram values
```

## Run the tests
```bash
.venv/bin/python -m pytest -q
```

## Run it
Run from the project root with `PYTHONPATH=.` (or set it once in your shell):
```bash
.venv/bin/python scripts/healthcheck.py                # verify Alpaca + Telegram
.venv/bin/python scripts/backtest.py AAPL 30           # backtest a symbol over ~30 days
.venv/bin/python scripts/run_bot.py --dry-run --force  # scan now, show intended trades (no orders)
.venv/bin/python scripts/run_bot.py                    # trade live (paper), continuously
.venv/bin/python scripts/dashboard.py                  # stats dashboard -> http://127.0.0.1:8787
```

## Status
- [x] Strategy engine (SMC detectors) + tests
- [x] Risk engine (3% risk, structural stop + 10% hard cap, daily kill-switch)
- [x] Alpaca data + paper execution (bracket orders, verified)
- [x] Telegram alerts (verified)
- [x] Backtester
- [x] Stats dashboard
- [x] Auto-reconcile closed trades into the journal (win/loss fills in automatically)
- [x] End-of-day flatten (never hold overnight)
- [ ] Deploy to an always-on host  ← next (the "trade while away" piece)
- [ ] Universe screener ("go find" stocks beyond the watchlist)
