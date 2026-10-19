"""Conservative exit-risk decision for ATLAS paper signals only.

A stale or unverified quote never creates a SELL. SELL is an advisory
paper exit marker, not a broker instruction or evidence of an executed fill.
"""
from datetime import datetime, timezone
import math

def paper_exit_decision(*, entry_price, current_price, stop_price, target_price,
                        feed_verified, observed_at_utc, now,
                        invalidated=False):
    def result(signal,reason):
        return {"signal":signal,"reason":reason,"orders_enabled":False,
                "paper_exit_executed":False}
    if now.tzinfo is None:
        raise ValueError("timezone-aware now required")
    if feed_verified is not True or not isinstance(observed_at_utc,str):
        return result("WAIT","UNVERIFIED_FEED")
    try:
        stamp=datetime.fromisoformat(observed_at_utc.replace("Z","+00:00"))
        if stamp.tzinfo is None:
            return result("WAIT","INVALID_TIMESTAMP")
        age=(now.astimezone(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
    except (ValueError,OverflowError):
        return result("WAIT","INVALID_TIMESTAMP")
    if not 0<=age<=10:
        return result("WAIT","STALE_OR_FUTURE_QUOTE")
    try:
        entry,px,stop,target=map(float,(entry_price,current_price,stop_price,target_price))
    except (TypeError,ValueError,OverflowError):
        return result("WAIT","INVALID_PRICES")
    if not all(math.isfinite(x) and x>0 for x in (entry,px,stop,target)) or not stop<entry<target:
        return result("WAIT","INVALID_RISK_LEVELS")
    if invalidated is True:
        return result("SELL","SIGNAL_INVALIDATED")
    if px<=stop:
        return result("SELL","STOP_BREACHED")
    if px>=target:
        return result("SELL","TARGET_REACHED")
    return result("WAIT","NO_EXIT_TRIGGER")
