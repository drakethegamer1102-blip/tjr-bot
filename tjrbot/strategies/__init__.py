"""Non-SMC strategies that run alongside TJR (each returns tagged Signals).

Each strategy exposes ``generate(today, **params) -> list[Signal]`` operating on a
single session's intraday bars. Signals carry `.strategy` and `.entry_type` so the
engine, backtester, and per-strategy stats can treat them uniformly.
"""

from . import orb, vwap_rev

REGISTRY = {
    "orb": orb.generate,
    "vwap_rev": vwap_rev.generate,
}

__all__ = ["orb", "vwap_rev", "REGISTRY"]
