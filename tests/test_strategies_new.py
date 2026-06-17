"""Tests for the ORB and VWAP-reversion strategies."""

import pandas as pd

from tjrbot.strategies import orb, vwap_rev


def make_day(rows, start="2026-06-10 09:30"):
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000
    return df


def test_orb_long_breakout():
    bars = make_day(
        [
            (100, 101, 99, 100),       # 9:30 opening range
            (100, 101, 99.5, 100.5),   # 9:35 opening range
            (100.5, 101, 100, 100.8),  # 9:40 opening range (ends 9:45: ORH=101, ORL=99)
            (100.8, 102.5, 100.7, 102.2),  # 9:45 breakout: close 102.2 > 101 and > VWAP
            (102.2, 103, 101.5, 102.5),
        ]
    )
    sigs = orb.generate(bars, or_minutes=15, min_rr=2.0)
    longs = [s for s in sigs if s.side == "long"]
    assert len(longs) >= 1
    s = longs[0]
    assert s.index == 3 and abs(s.stop - 99.0) < 1e-9
    assert s.strategy == "orb" and s.entry_type == "market"


def test_vwap_rev_long_fires_gap_up_session():
    # Gap-up session: price opens far above VWAP (established by pre-market avg near open).
    # Simulate by injecting pre-market bars at 100, then RTH bars at 120 which dip to 112.
    # VWAP anchored near 100 from pre-market, RTH dip to 112 is still above VWAP(100)...
    # Actually simplest approach: build bars where early price is low (anchoring VWAP low),
    # then price rises (EMA rises with it), then a moderate dip to between VWAP and EMA.
    # Use ema_period=2 (reactive) and a scenario where VWAP dips below EMA at the right bar.
    rows = []
    # bars 0-14: rising 90→104, VWAP ~97, EMA(2) tracks closely
    for i in range(15):
        p = 90.0 + i
        rows.append((p - 0.2, p + 0.3, p - 0.3, p))
    # bars 15-19: hold at 104 — VWAP rises toward 100, EMA(2) = 104
    for _ in range(5):
        rows.append((104, 104.5, 103.5, 104))
    # bar 20: dip to 101 — VWAP ~100.5, EMA(2) ~102.7; c(101) > EMA? No: 101 < 102.7
    # Try dip to 102: EMA(2) ~ 103; 102 < 103, still fails.
    # Use very gentle dip so EMA(2) barely drops: dip to 103
    rows.append((104, 104, 102.5, 103))
    # At bar 20: EMA(2) of [104,103] = 104*(1-2/3) + 103*(2/3) = 34.67+68.67=103.33? No
    # EMA(2): k=2/(2+1)=0.667; EMA = prev*0.333 + cur*0.667
    # prev EMA = 104; cur = 103: EMA = 104*0.333 + 103*0.667 = 34.63 + 68.7 = 103.33
    # close=103, EMA=103.33 -> c>EMA? 103 < 103.33: False. Still blocked.
    # The EMA(2) is TOO reactive. Need to use a different design for tests.
    #
    # CONCLUSION: The EMA trend filter `c > EMA for longs` doesn't fire on simple
    # synthetic patterns because the bar that dips below VWAP also dips below EMA.
    # This is actually correct behavior — the filter requires the stock to still be
    # in uptrend (close > EMA) even while touching VWAP. In practice this fires on
    # intraday pullbacks where price dips to VWAP but the short-term trend is still up.
    # Test this by constructing: flat base at 100 (VWAP=100, EMA=100), then 1 bar dip
    # to 98 (RSI drops, c < VWAP=100), but EMA(2)=99 so c(98) < EMA(99)... fails.
    #
    # The ONLY way c > EMA and c < VWAP simultaneously is if VWAP > EMA at that bar.
    # VWAP > EMA when session opened high and price declined — VWAP anchors the high
    # session average above the declining EMA. Use ema_period=2 with high opening:
    rows = []
    # bars 0-14: flat at 115, VWAP=115, EMA(2)→115
    for _ in range(15):
        rows.append((115, 115.5, 114.5, 115))
    # bars 15-19: gradual decline to 110, EMA(2) drops fast to ~110, VWAP stays ~114
    for i in range(5):
        p = 115 - (i+1)*1.0
        rows.append((p+0.2, p+0.5, p-0.5, p))
    # bar 20: bounce to 111.5 — VWAP ~113.7, EMA(2)~110.9; c=111.5 > EMA=110.9 ✓
    # and c=111.5 < VWAP=113.7 ✓ → RSI needs to be < rsi_lo
    rows.append((110, 112, 110, 111.5))

    sigs = vwap_rev.generate(
        make_day(rows),
        atr_mult=0.2,
        rsi_lo=50,
        rsi_period=10,
        ema_period=2,
        min_bars_open=0,
        vol_mult=0,  # synthetic bars have flat volume; disable filter in unit tests
    )
    longs = [s for s in sigs if s.side == "long"]
    assert len(longs) >= 1, "expected long: c > EMA(2) and c < VWAP after decline"
    assert longs[0].strategy == "vwap_rev" and longs[0].entry_type == "market"


def test_vwap_rev_trend_filter_blocks_counter_trend():
    # Pure uptrend (monotonic ramp): EMA tracks above, so short should be blocked.
    rows = [(100 + 2*i, 100 + 2*i + 0.5, 100 + 2*i - 0.5, 100 + 2*i) for i in range(25)]
    sigs = vwap_rev.generate(
        make_day(rows), atr_mult=0.5, rsi_hi=55, rsi_period=14, ema_period=10, min_bars_open=0, vol_mult=0
    )
    shorts = [s for s in sigs if s.side == "short"]
    assert len(shorts) == 0, "trend filter must block shorts in a pure uptrend"


def test_vwap_rev_min_bars_open():
    rows = [(100 + 2*i, 100 + 2*i + 0.5, 100 + 2*i - 0.5, 100 + 2*i) for i in range(25)]
    sigs = vwap_rev.generate(
        make_day(rows), atr_mult=0.5, rsi_hi=50, rsi_period=14, ema_period=10, min_bars_open=99, vol_mult=0
    )
    assert len(sigs) == 0, "min_bars_open=99 must suppress all signals"
