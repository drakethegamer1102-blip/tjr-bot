# Crypto strategy research — 3 new DAILY crypto edges

Built 2026-08-10. After the intraday losers (ORB, squeeze, ORB-futures) proved to have no
edge, a battery test across NEW asset classes (bonds, gold, silver, sector ETFs, crypto)
found CRYPTO as the standout: the one asset class where momentum/breakout genuinely works,
because crypto is a trending, less-efficient, 24/7 market. Gold/silver failed (no clean
edge); bonds were modest; crypto was strong across the board.

## The 3 (validated on BTC-USD + ETH-USD daily, all-era robust)
| Name | Rule | BTC+ETH PF | Mechanism |
|------|------|-----------|-----------|
| **MOONSHOT** | 20-day-high breakout, Close > 200d SMA | 1.83 | momentum/breakout |
| **CRYPTODIP** | 10-day-low dip, 50d SMA > 200d (golden) | 1.77 | dip-buy in uptrend |
| **CRYPTORSI** | RSI(2) < 5 oversold, Close > 200d SMA | 1.54 | oversold reversal |

Distinct: BREAKOUT has 0% trigger overlap with the two dip strategies (momentum vs
mean-reversion); the two dips overlap 39%. 2-year paper backfill (BTC+ETH, $10k/trade):
MOONSHOT +$1,631, CRYPTORSI +$1,881, CRYPTODIP +$267 — combined +$3,779.

## Why crypto (and not the others)
- **Momentum WORKS on crypto** — 20d-high breakout PF 1.83, where the SAME breakout LOSES
  on stocks/index-futures (efficient, mean-reverting markets). This is the key insight.
- **Alpaca already trades BTC/USD + ETH/USD** (get_crypto_bars + a crypto profile exist),
  24/7, no PDT rule — so these can go live on the existing account.
- Gold/silver: no era-robust edge (PF < 1.1). Bonds: a couple modest edges only.

## Honest caveats
- SELECTIVE + BURSTY: last signals were 2025-10/11; crypto goes through quiet stretches.
  The edge is real (validated) but patient — it won't trade steadily.
- Only ~10 years of crypto history (vs 26y for ES) — a shorter, more regime-limited sample.
- Paper only. Watch forward before real money, same discipline as everything else.

Files: tjrbot/strategies/crypto_daily.py · scripts/crypto_daily_paper.py ·
tests/test_crypto_daily.py · ledger crypto_daily_ledger.json. Runs in the after-close
digest; own Telegram message (🪙 CRYPTO · DAILY).
