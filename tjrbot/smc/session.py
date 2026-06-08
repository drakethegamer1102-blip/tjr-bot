"""Trading session / ICT-style killzone time windows (US/Eastern)."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# (start, end) in ET. A window where start > end wraps past midnight.
KILLZONES: dict[str, tuple[dt.time, dt.time]] = {
    "asia": (dt.time(19, 0), dt.time(22, 0)),
    "london": (dt.time(2, 0), dt.time(5, 0)),
    "ny": (dt.time(7, 0), dt.time(10, 0)),  # ICT New York killzone
    "ny_open": (dt.time(9, 30), dt.time(11, 30)),  # stock NY-open window (TJR's bread & butter)
    "rth": (dt.time(9, 30), dt.time(16, 0)),  # regular US stock hours
}


def in_session(ts, names: list[str]) -> bool:
    """True if timestamp `ts` (tz-aware or naive=UTC) falls in any named window."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    t = ts.astimezone(ET).time()
    for name in names:
        start, end = KILLZONES[name]
        if start <= end:
            if start <= t < end:
                return True
        else:  # window wraps midnight
            if t >= start or t < end:
                return True
    return False
