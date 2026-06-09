"""Tests for the screener's filter/rank logic (pure, no API)."""

from tjrbot.data.screener import rank_candidates


def test_rank_filters_and_orders():
    # vol = shares; ranking is by DOLLAR volume (price * shares)
    vol = {"NVDA": 3e8, "AAPL": 4e8, "PENNY": 2e9, "BRKA": 1e6, "SOXL": 3e9, "MID": 1e7}
    price = {"NVDA": 130.0, "AAPL": 300.0, "PENNY": 0.03, "BRKA": 600000.0, "SOXL": 25.0, "MID": 50.0}
    out = rank_candidates(
        vol, price, min_price=5.0, max_price=1000.0, max_symbols=10, deny={"SOXL"}
    )
    assert "PENNY" not in out      # below min_price
    assert "BRKA" not in out       # above max_price ($600k) and not a normal stock
    assert "SOXL" not in out       # leveraged (denylist)
    # dollar volumes: AAPL 1.2e11 > NVDA 3.9e10 > MID 5e8
    assert out == ["AAPL", "NVDA", "MID"]


def test_rank_respects_max_symbols():
    vol = {"A": 5, "B": 4, "C": 3}
    price = {"A": 10, "B": 10, "C": 10}
    out = rank_candidates(vol, price, min_price=1, max_price=100, max_symbols=2)
    assert out == ["A", "B"]
