"""SQLite trade journal — records order intents and closed trades for the dashboard."""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "state" / "journal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    client_order_id TEXT PRIMARY KEY,
    alpaca_order_id TEXT,
    symbol TEXT, side TEXT,
    entry REAL, stop REAL, target REAL, qty REAL,
    status TEXT, reasons TEXT, submitted_at TEXT
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT,
    symbol TEXT, side TEXT,
    entry REAL, exit REAL, qty REAL,
    pnl REAL, outcome TEXT,
    opened_at TEXT, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, level TEXT, message TEXT
);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Journal:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def has_order(self, coid: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM orders WHERE client_order_id=?", (coid,)
        ).fetchone() is not None

    def has_trade(self, coid: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM trades WHERE client_order_id=?", (coid,)
        ).fetchone() is not None

    def record_order(self, coid, alpaca_id, symbol, side, entry, stop, target, qty, status, reasons):
        self.conn.execute(
            "INSERT OR REPLACE INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (coid, alpaca_id, symbol, side, entry, stop, target, qty, status,
             ",".join(reasons or []), _now()),
        )
        self.conn.commit()

    def record_trade(self, coid, symbol, side, entry, exit_, qty, pnl, outcome, opened_at, closed_at):
        self.conn.execute(
            "INSERT INTO trades (client_order_id,symbol,side,entry,exit,qty,pnl,outcome,opened_at,closed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (coid, symbol, side, entry, exit_, qty, pnl, outcome, opened_at, closed_at),
        )
        self.conn.commit()

    def log(self, level: str, message: str) -> None:
        self.conn.execute(
            "INSERT INTO events (ts,level,message) VALUES (?,?,?)", (_now(), level, message)
        )
        self.conn.commit()

    def trades(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM trades ORDER BY id DESC"))

    def open_orders(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM orders ORDER BY submitted_at DESC LIMIT 50"))

    def stats(self) -> dict:
        rows = list(self.conn.execute("SELECT pnl, outcome FROM trades"))
        n = len(rows)
        wins = [r for r in rows if r["pnl"] and r["pnl"] > 0]
        losses = [r for r in rows if r["pnl"] and r["pnl"] < 0]
        gw = sum(r["pnl"] for r in wins)
        gl = -sum(r["pnl"] for r in losses)
        return {
            "trades": n,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / n) if n else 0.0,
            "avg_win": (gw / len(wins)) if wins else 0.0,
            "avg_loss": (gl / len(losses)) if losses else 0.0,
            "profit_factor": (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0.0),
            "net_pnl": sum(r["pnl"] for r in rows if r["pnl"] is not None),
        }
