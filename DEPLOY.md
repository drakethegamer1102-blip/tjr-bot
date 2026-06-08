# Deploying the bot for free (GitHub Actions)

This runs your bot on GitHub's free scheduled runners — no server, no credit card,
nothing on your Mac. Telegram alerts work the same. The dashboard you run locally
whenever you want to look (`scripts/dashboard.py`).

## How it works
- A scheduled workflow (`.github/workflows/trade.yml`) runs `run_bot.py --once`
  every 5 minutes during US market hours.
- Each run: reconciles closed trades → flattens at end of day → scans for setups →
  places paper bracket orders → pings Telegram.
- **Idempotent:** orders use a unique id per setup; Alpaca rejects duplicates, so a
  repeated run never double-trades. The bot is effectively *stateless* — Alpaca is
  the source of truth, so it's safe to run as isolated jobs.
- **Secrets** (Alpaca keys, Telegram token) live as encrypted GitHub Actions
  secrets — never in the code.

## One-time setup
1. Create a GitHub repo (private is fine).
2. Push this project to it (`.env` and `state/` are gitignored — secrets never leave your machine).
3. Add these repo secrets (Settings → Secrets and variables → Actions):
   `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET`, `ALPACA_PAPER` (=`true`),
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. Enable Actions, then **Run workflow** once (Actions tab → TJR Bot → Run workflow)
   to confirm it connects to Alpaca cleanly.

## Daylight-saving note
The cron times are set for **EDT (summer)**. In **winter (EST)**, edit
`.github/workflows/trade.yml` and shift both windows **+1 hour**
(`13-15` → `14-16`, `19-20` → `20-21`).

## Free-minutes note
A private repo gets 2,000 free Action-minutes/month; the current schedule uses
roughly 1,600 — comfortably under. If you ever hit the limit, either narrow the
cron window or make the repo public (public repos get unlimited Action minutes,
and your secrets stay encrypted either way).

## Pause / stop
Actions tab → TJR Bot → "⋯" → **Disable workflow**. Re-enable anytime.

## Upgrade path (later)
For a true always-on server (continuous loop + hosted dashboard + tighter timing),
an Oracle Cloud or Google Cloud **Always Free** VM is $0 but needs a credit card to
verify the account. Say the word and I'll set that up instead.
