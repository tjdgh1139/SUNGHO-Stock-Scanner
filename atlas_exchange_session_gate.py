"""Fail-closed exchange session gate for ATLAS staging.

No embedded holiday guesses: caller must supply a VERIFIED session-date
allowlist from a licensed exchange calendar. Does not start a scheduler,
request market data, or place orders.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

MARKETS = {
    "KRX": ("Asia/Seoul", time(9, 0), time(15, 30)),
    "NYSE": ("America/New_York", time(9, 30), time(16, 0)),
    "NASDAQ": ("America/New_York", time(9, 30), time(16, 0)),
}

def market_gate(market: str, now_utc: datetime, *,
                verified_open_dates: set[str] | None,
                verified_early_closes: dict[str, str] | None = None) -> dict:
    if market not in MARKETS:
        return {"open": False, "reason": "UNSUPPORTED_MARKET"}
    if now_utc.tzinfo is None:
        return {"open": False, "reason": "NAIVE_CLOCK"}
    tz_name, start, default_end = MARKETS[market]
    local = now_utc.astimezone(ZoneInfo(tz_name))
    day = local.date().isoformat()
    if verified_open_dates is None:
        return {"open": False, "reason": "CALENDAR_NOT_VERIFIED"}
    if day not in verified_open_dates:
        return {"open": False, "reason": "NOT_VERIFIED_OPEN_DATE", "local_date": day}
    early = (verified_early_closes or {}).get(day)
    try:
        end = time.fromisoformat(early) if early else default_end
    except ValueError:
        return {"open": False, "reason": "INVALID_EARLY_CLOSE"}
    if end <= start:
        return {"open": False, "reason": "INVALID_SESSION"}
    if start <= local.time().replace(tzinfo=None) < end:
        return {"open": True, "reason": "VERIFIED_REGULAR_SESSION", "local_date": day}
    return {"open": False, "reason": "OUTSIDE_REGULAR_SESSION", "local_date": day}
