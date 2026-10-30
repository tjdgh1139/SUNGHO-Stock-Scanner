"""ATLAS research-only quote quality assessment.

Never turns missing or stale quotes into BUY signals. No trading orders.
"""
from datetime import datetime, timezone

def assess_quote(quote: dict | None, *, now_utc: str, max_age_seconds: int = 120) -> dict:
    if not quote:
        return {"usable": False, "reason": "MISSING"}
    try:
        observed = datetime.fromisoformat(str(quote["received_at_utc"]).replace("Z", "+00:00"))
        now = datetime.fromisoformat(now_utc.replace("Z", "+00:00"))
        if observed.tzinfo is None or now.tzinfo is None:
            return {"usable": False, "reason": "TIMEZONE_MISSING"}
        age = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
        if age < -5:
            return {"usable": False, "reason": "FUTURE_TIMESTAMP"}
        if age > max_age_seconds:
            return {"usable": False, "reason": "STALE"}
        if float(quote["price"]) <= 0:
            return {"usable": False, "reason": "INVALID_PRICE"}
        return {"usable": True, "reason": "OK", "age_seconds": age}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"usable": False, "reason": "INVALID_DATA"}
