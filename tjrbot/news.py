"""Alpaca (Benzinga) news: fresh-headline lookups for the news gate + morning digest.

Free with the existing Alpaca keys. Two consumers:
  - engine.scan_once: symbols with a fresh headline get their mean-reversion (RIPTIDE)
    signals dropped — news-driven moves are exactly the moves that run over a fade.
  - scripts/morning_brief.py: a pre-open Telegram digest of watchlist headlines.
Both are failure-safe: any API problem degrades to "no news", never blocks trading.
"""

from __future__ import annotations

import datetime as dt


def fetch_headlines(
    key: str,
    secret: str,
    symbols: list[str],
    hours: float = 18,
    limit: int = 50,
) -> dict[str, list[str]]:
    """symbol -> headlines from the last `hours`, newest first.

    A story tagged with several watched symbols appears under each of them.
    Returns {} on any API error (fail-open: no news signal, trading unaffected).
    """
    from alpaca.data.historical.news import NewsClient
    from alpaca.data.requests import NewsRequest

    want = {sym.replace("/", "") for sym in symbols}
    if not want:
        return {}
    try:
        client = NewsClient(key, secret)
        req = NewsRequest(
            symbols=",".join(sorted(want)),
            start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours),
            limit=limit,
        )
        items = client.get_news(req).data.get("news", [])
    except Exception:  # noqa: BLE001 - news must never take down a scan
        return {}
    out: dict[str, list[str]] = {}
    for n in items:
        headline = str(getattr(n, "headline", "") or "").strip()
        if not headline:
            continue
        for sym in getattr(n, "symbols", None) or []:
            if sym in want:
                out.setdefault(sym, []).append(headline)
    return out
