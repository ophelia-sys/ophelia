"""Session model, IST blackout, daily reset (all UTC-canonical internally)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from datetime import time as dtime

IST = timezone(timedelta(hours=5, minutes=30))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_ist() -> datetime:
    return now_utc().astimezone(IST)


def current_sessions(utc_dt=None) -> list[str]:
    u = (utc_dt or now_utc()).time()
    out = []
    if dtime(0, 0) <= u < dtime(9, 0):
        out.append("ASIA")
    if dtime(7, 0) <= u < dtime(16, 0):
        out.append("LONDON")
    if dtime(12, 0) <= u < dtime(21, 0):
        out.append("NEW_YORK")
    return out


def in_blackout(ist_dt: datetime | None = None) -> bool:
    """Hard new-trade blackout 02:30-05:30 IST."""
    t = (ist_dt or now_ist()).time()
    return dtime(2, 30) <= t < dtime(5, 30)


def ist_now_str() -> str:
    return now_ist().strftime("%Y-%m-%d %H:%M:%S IST")


def next_daily_reset_ist() -> str:
    n = now_ist()
    reset = n.replace(hour=5, minute=30, second=0, microsecond=0)
    if n >= reset:
        reset += timedelta(days=1)
    return reset.strftime("%Y-%m-%d %H:%M IST")


def session_note() -> dict:
    return {"sessions_active_utc": current_sessions(),
            "blackout_new_entries": in_blackout(),
            "next_daily_reset_ist": next_daily_reset_ist()}
