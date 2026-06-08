# Automated Trading Bot — Project Plan

_Last updated: 2026-06-08. This is a living document. Nothing here is final until you confirm._

---

## 1. The honest constraints (read this first)

**a) I cannot watch the 56 TJR videos.** This isn't about permission — I can't process video or audio at all. So instead I researched TJR's *published* strategy (community notes, strategy write-ups, and the open-source TradingView indicators that mechanize his model) and reconstructed his rules below. **Please check Section 3 and correct anything I got wrong.** If there's nuance only in the videos, you can paste transcripts or notes and I'll fold them in. (There are detailed community PDFs of the bootcamp I can also read if you want.)

**b) "Very precise, no errors" — what's actually achievable.** I want to be clear so you're not surprised later:
- **I *can* make the *code* precise:** exact rule logic, correct position sizing and stops, no duplicate/double orders, reconnect handling, a hard kill-switch, full logging of every decision, and validation against historical data (backtest) + paper trading before any real money.
- **I *cannot* make the *trades* error-free or guarantee profit.** No bot can. Markets are partly random and adversarial. Even an excellent strategy loses on a large share of trades and has losing streaks. Day trading specifically: most retail day traders lose money. Starting on paper (fake money, real data) is exactly the right way to measure whether this actually works before risking a cent.

**c) It must run on an always-on machine.** "Trade even while I'm not at my computer" means the bot **cannot live on your Mac** (it stops when the Mac sleeps). It needs a cheap always-on host — a small cloud server (~$5/mo) or a Raspberry Pi at home. We'll build and test locally first, then deploy.

---

## 2. The catch with TJR + Alpaca + stocks

TJR's strategy is **Smart Money Concepts (SMC / ICT-style)** and is built for **24-hour markets** — forex, futures, indices, crypto. The core "sweep the Asia-session high/low during the London/New-York session" model only makes sense in a market that trades overnight.

**Two problems:**
1. **Alpaca cannot trade forex or futures.** It trades **US stocks/ETFs, options, and crypto** only. So TJR's native instruments (e.g. NAS100, EUR/USD) aren't available here.
2. **Individual US stocks don't have an "Asia session."** They trade ~9:30am–4:00pm ET. TJR's session model doesn't map onto them cleanly.

**So we have a real choice (see decision in Section 7):**
- **Crypto** on Alpaca trades 24/7 → fits TJR's *exact* session-sweep model best.
- **US stocks** → I adapt the SMC concepts to the regular session (use prior-day high/low and the opening-range as the "liquidity" that gets swept). This is a legitimate, well-known intraday approach, but it's an *adaptation* of TJR, not his literal model.

---

## 3. TJR's strategy, as I understand it (CONFIRM / CORRECT ME)

A Smart-Money / liquidity model. The mechanical version:

1. **Higher-timeframe bias:** Read weekly → daily → 4h → 1h to decide a directional lean (looking for longs or shorts).
2. **Mark key liquidity levels:** session range high/low (Asia range, default 8pm–12am ET), prior-day high/low, recent swing highs/lows. These are where stops cluster.
3. **Wait for a liquidity sweep:** during the active session, price pierces one of those levels (grabbing stops) and then rejects.
4. **Confirm with a Market Structure Shift (MSS) / Break of Structure (BOS):** price closes back through the most recent swing point. *Pivot strength* tunes this — 1 = aggressive, 3+ = conservative.
5. **Enter on the retracement** into a **Fair Value Gap (FVG)** (a 3-candle imbalance, filtered by ATR so tiny gaps are ignored), an **Order Block**, or the MSS / 50% equilibrium level.
6. **Stop loss:** just beyond the swept extreme. **Targets:** opposing liquidity; take partial profits along the way.
7. **Risk:** ~1% of account per trade; often just 1 high-quality trade per day.

> **Reality check on automation:** sweeps, order blocks, and structure shifts are partly *discretionary* — TJR reads them by eye. Mechanizing them (as the TradingView indicators do, and as I would) produces a faithful *approximation*, not a perfect copy of his judgment. The backtest will tell us how good the approximation is.

---

## 4. Your risk rule — I need to confirm what you meant

You said: *"Stop-loss = 20% below what is risked. So make sure to keep 80%."*

For **day trading**, a 20%-per-position stop is extremely wide (day-trade stops are usually a fraction of a percent to a few percent), so I want to make sure I implement what you actually want. Two readings:

- **(A) Position stop:** exit a trade if it falls 20% from entry — i.e. never lose more than 20% *of the money in that one trade*.
- **(B) Account risk:** only ever put a small slice of the account at risk per trade and keep the rest safe.

**My recommendation (the professional approach, also what TJR does):** risk a small fixed **% of the account per trade** (default **1%**), place the stop at the structural level (just past the swept high/low), and size the position so that hitting that stop = that 1%. This protects your account far better than a flat 20% position stop. **All of this will be configurable** — tell me if you want a hard 20% cap too and I'll add it. (It's paper money to start, so we can experiment safely.)

---

## 5. Architecture

```
                 ┌─────────────────────────────────────────┐
 Always-on host  │  SCANNER (loops during session)          │
 (cloud / Pi)    │   • pulls OHLC bars from Alpaca           │
                 │   • detects sweep → MSS/BOS → FVG/OB      │
                 │   • scores & ranks candidates            │
                 └───────────────┬──────────────────────────┘
                                 │ signal
                 ┌───────────────▼──────────────────────────┐
                 │  RISK ENGINE                              │
                 │   • position size from account-risk %     │
                 │   • stop / target placement               │
                 │   • daily loss limit + kill-switch        │
                 └───────────────┬──────────────────────────┘
                                 │ approved order
                 ┌───────────────▼──────────────────────────┐
                 │  EXECUTION (Alpaca paper API)             │
                 │   • idempotent orders (no duplicates)     │
                 │   • bracket order: entry + stop + target  │
                 └───────────────┬──────────────────────────┘
              ┌──────────────────┼───────────────────┐
              ▼                  ▼                   ▼
        Phone push          Trade log            Stats dashboard
       (every action)    (full audit trail)   (win/loss, P&L, etc.)
```

- **Backtester:** runs the exact same rules over historical data so we can measure the strategy *before* trading.
- **Stats dashboard (plain & clear, as you asked):** win/loss ratio, total trades, average win vs. average loss, profit factor, largest win/loss, current & max drawdown, P&L today / this week / all-time, and the open positions. A simple local web page.

**Proposed stack:** Python (the standard for this — pandas for data, `alpaca-py` for the broker, a lightweight backtest, and a small Flask/FastAPI dashboard). You already have Python + pip available. Tell me if you'd rather it be in TypeScript/Node.

---

## 6. What I need you to connect / show me

| # | What | How to get it | Needed for |
|---|------|---------------|------------|
| 1 | **Alpaca account + PAPER API keys** (Key ID + Secret) | Sign up at alpaca.markets → switch to **Paper Trading** → "Generate API Keys". Give them to me (or put in a `.env` file). | Everything |
| 2 | **Telegram bot token + your chat ID** | Create a bot via @BotFather; get your chat ID from @userinfobot. | Phone alerts |
| 3 | **Market-data note** | Alpaca's free feed is **IEX only** (thinner data). Full real-time market data (**SIP**) is a paid Alpaca subscription. IEX is fine to start on paper. | Signal quality |
| 4 | **Risk confirmation** | Confirm Section 4 (per-trade risk %, and whether you want a hard 20% cap). | Risk engine |
| 5 | **Always-on host** (later) | Cloud VPS (~$5/mo) or a Raspberry Pi. I'll help you set it up once the bot works locally. | 24/7 trading |

---

## 7. Decisions made
- **Markets:** ✅ **Both** — US stocks (market hours) + crypto (24/7), switchable by config. Default to stocks.
- **Notifications:** ✅ **Telegram bot** (free; token + chat ID needed).

---

## 8. Roadmap

1. **Phase 0 — Setup:** confirm decisions, get Alpaca paper keys, scaffold the project.
2. **Phase 1 — Engine + backtest:** build SMC detection (sweep/MSS/FVG/OB) and the risk engine; backtest on history; show you results. **Build on real money risk = $0.**
3. **Phase 2 — Paper live:** run on the always-on host against live data with fake money; phone alerts; stats dashboard. Measure real win/loss for weeks.
4. **Phase 3 — Review:** look at the numbers together. *Only* if the paper results justify it do we discuss real money — and that's your decision, made with eyes open.
