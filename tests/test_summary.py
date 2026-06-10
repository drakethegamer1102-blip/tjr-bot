"""Tests for the summary aggregation (pure)."""

from tjrbot.engine import summarize_trades


def test_summarize_trades():
    trades = [
        {"symbol": "AAPL", "pnl": 100.0, "dt": None},
        {"symbol": "MSFT", "pnl": -40.0, "dt": None},
        {"symbol": "NVDA", "pnl": 250.0, "dt": None},
    ]
    r = summarize_trades(trades)
    assert r["n"] == 3 and r["wins"] == 2 and r["losses"] == 1
    assert abs(r["net"] - 310.0) < 1e-9
    assert r["best"]["symbol"] == "NVDA"
    assert r["worst"]["symbol"] == "MSFT"
    assert abs(r["win_rate"] - (2 / 3 * 100)) < 1e-6


def test_summarize_trades_empty():
    r = summarize_trades([])
    assert r["n"] == 0 and r["wins"] == 0 and r["losses"] == 0
    assert r["net"] == 0.0 and r["best"] is None and r["worst"] is None
