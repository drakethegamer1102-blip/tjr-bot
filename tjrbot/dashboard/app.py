"""A simple, readable dashboard: how the bot is doing, in plain English.

Reads your live Alpaca account (equity, today's change, open positions) and the
trade journal (win rate and trade stats). Auto-refreshes every 30 seconds.
"""

from __future__ import annotations

import datetime as dt

from flask import Flask, render_template_string

from ..config import load_settings
from ..journal import Journal
from ..reconcile import reconcile

PAGE = """
<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>TJR Bot — Dashboard</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: -apple-system, system-ui, sans-serif; background:#0e1117; color:#e6e6e6;
         margin:0; padding:24px; }
  h1 { font-size:20px; font-weight:600; margin:0 0 4px; }
  .sub { color:#8b949e; font-size:13px; margin-bottom:20px; }
  .tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; }
  .tile { background:#161b22; border:1px solid #232a33; border-radius:12px; padding:18px; }
  .tile .label { color:#8b949e; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  .tile .value { font-size:28px; font-weight:700; margin-top:6px; }
  .pos { color:#3fb950; } .neg { color:#f85149; } .muted { color:#8b949e; }
  table { width:100%; border-collapse:collapse; margin-top:14px; }
  th,td { text-align:left; padding:10px 12px; border-bottom:1px solid #232a33; font-size:14px; }
  th { color:#8b949e; font-weight:500; font-size:12px; text-transform:uppercase; }
  .card { background:#161b22; border:1px solid #232a33; border-radius:12px; padding:8px 16px 16px; margin-top:22px; }
  .card h2 { font-size:15px; font-weight:600; }
  .empty { color:#8b949e; padding:14px 12px; font-size:14px; }
  .foot { color:#6b7480; font-size:12px; margin-top:24px; }
</style></head><body>
  <h1>🤖 TJR Bot — {{ mode }}</h1>
  <div class="sub">Profile: {{ profile }} · updated {{ updated }} · refreshes every 30s</div>

  <div class="tiles">
    <div class="tile"><div class="label">Account Equity</div><div class="value">{{ equity }}</div></div>
    <div class="tile"><div class="label">Today's P&amp;L</div><div class="value {{ today_cls }}">{{ today }}</div></div>
    <div class="tile"><div class="label">Total P&amp;L (since start)</div><div class="value {{ total_cls }}">{{ total }}<span style="font-size:15px"> ({{ total_pct }})</span></div></div>
    <div class="tile"><div class="label">Win Rate</div><div class="value">{{ win_rate }}<span style="font-size:14px" class="muted"> ({{ wins }}W / {{ losses }}L)</span></div></div>
  </div>

  <div class="card">
    <h2>Open Positions</h2>
    {% if positions %}
    <table><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Avg Entry</th><th>Current</th><th>Unrealized P&amp;L</th></tr>
      {% for p in positions %}
      <tr><td>{{ p.symbol }}</td><td>{{ p.side }}</td><td>{{ p.qty }}</td><td>{{ p.entry }}</td>
          <td>{{ p.current }}</td><td class="{{ p.cls }}">{{ p.upl }} ({{ p.uplpc }})</td></tr>
      {% endfor %}
    </table>
    {% else %}<div class="empty">No open positions right now.</div>{% endif %}
  </div>

  <div class="card">
    <h2>Trading Stats</h2>
    <table>
      <tr><td>Total trades</td><td>{{ stats.trades }}</td></tr>
      <tr><td>Win rate</td><td>{{ win_rate }}</td></tr>
      <tr><td>Average win</td><td class="pos">{{ stats.avg_win }}</td></tr>
      <tr><td>Average loss</td><td class="neg">{{ stats.avg_loss }}</td></tr>
      <tr><td>Profit factor</td><td>{{ stats.profit_factor }} <span class="muted">(&gt;1 = making money)</span></td></tr>
      <tr><td>Net realized P&amp;L</td><td class="{{ stats.net_cls }}">{{ stats.net_pnl }}</td></tr>
    </table>
    {% if stats.trades == 0 %}<div class="empty">No closed trades yet — this fills in automatically as the bot trades.</div>{% endif %}
  </div>

  <div class="card">
    <h2>Recent Orders</h2>
    {% if orders %}
    <table><tr><th>Time (UTC)</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Stop</th><th>Target</th><th>Qty</th><th>Status</th></tr>
      {% for o in orders %}
      <tr><td>{{ o.t }}</td><td>{{ o.symbol }}</td><td>{{ o.side }}</td><td>{{ o.entry }}</td>
          <td>{{ o.stop }}</td><td>{{ o.target }}</td><td>{{ o.qty }}</td><td>{{ o.status }}</td></tr>
      {% endfor %}
    </table>
    {% else %}<div class="empty">No orders placed yet.</div>{% endif %}
  </div>

  <div class="foot">Paper trading. Numbers are live from Alpaca. This is not financial advice.</div>
</body></html>
"""


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _signed(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}${abs(x):,.2f}"


def create_app() -> Flask:
    app = Flask(__name__)
    settings = load_settings()
    start_equity = float(settings.get("start_equity", 100_000.0))

    @app.route("/")
    def home():  # noqa: ANN202
        journal = Journal()
        stats = journal.stats()

        equity = last_eq = start_equity
        positions: list[dict] = []
        mode = "Paper" if settings.alpaca_paper else "LIVE"
        try:
            from ..execution.alpaca_exec import Broker

            broker = Broker(settings.alpaca_key, settings.alpaca_secret, paper=settings.alpaca_paper)
            reconcile(broker, journal)
            acct = broker.account()
            equity = float(acct.equity)
            last_eq = float(acct.last_equity or equity)
            for p in broker.positions():
                upl = float(p.unrealized_pl)
                positions.append(
                    {
                        "symbol": p.symbol,
                        "side": str(p.side.value).upper(),
                        "qty": f"{float(p.qty):g}",
                        "entry": _money(float(p.avg_entry_price)),
                        "current": _money(float(p.current_price)),
                        "upl": _signed(upl),
                        "uplpc": f"{float(p.unrealized_plpc) * 100:+.1f}%",
                        "cls": "pos" if upl >= 0 else "neg",
                    }
                )
        except Exception as e:  # noqa: BLE001
            journal.log("error", f"dashboard: {e}")

        today_pl = equity - last_eq
        total_pl = equity - start_equity
        total_pct = (total_pl / start_equity * 100) if start_equity else 0.0
        pf = stats["profit_factor"]

        orders = [
            {
                "t": (o["submitted_at"] or "")[:16].replace("T", " "),
                "symbol": o["symbol"], "side": o["side"],
                "entry": _money(o["entry"]), "stop": _money(o["stop"]),
                "target": _money(o["target"]), "qty": f"{o['qty']:g}", "status": o["status"],
            }
            for o in journal.open_orders()
        ]

        return render_template_string(
            PAGE,
            mode=mode,
            profile=settings.profile_name,
            updated=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            equity=_money(equity),
            today=_signed(today_pl), today_cls="pos" if today_pl >= 0 else "neg",
            total=_signed(total_pl), total_cls="pos" if total_pl >= 0 else "neg",
            total_pct=f"{total_pct:+.1f}%",
            win_rate=f"{stats['win_rate'] * 100:.0f}%",
            wins=stats["wins"], losses=stats["losses"],
            positions=positions,
            stats={
                "trades": stats["trades"],
                "avg_win": _money(stats["avg_win"]),
                "avg_loss": "-" + _money(stats["avg_loss"]),
                "profit_factor": ("∞" if pf == float("inf") else f"{pf:.2f}"),
                "net_pnl": _signed(stats["net_pnl"]),
                "net_cls": "pos" if stats["net_pnl"] >= 0 else "neg",
            },
            orders=orders,
        )

    return app
