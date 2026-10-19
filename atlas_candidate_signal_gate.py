"""Fail-closed signal gate for ATLAS candidate presentation.

This is a display recommendation only, not a trading system or an order.
No verified fresh quote => WAIT; do not infer institutional flows from price.
"""
from datetime import datetime,timezone
import math

def candidate_decision(*, feed_verified, observed_at_utc, now,
                       price, score, volume_confirmed, sector_confirmed,
                       trend_confirmed, risk_blocked=False):
    if now.tzinfo is None:
        raise ValueError("timezone-aware now required")
    def wait(reason):
        return {"signal":"WAIT","reason":reason,"orders_enabled":False}
    if feed_verified is not True or not isinstance(observed_at_utc,str):
        return wait("UNVERIFIED_FEED")
    try:
        stamp=datetime.fromisoformat(observed_at_utc.replace("Z","+00:00"))
        if stamp.tzinfo is None:
            return wait("INVALID_TIMESTAMP")
        age=(now.astimezone(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
    except (ValueError,OverflowError):
        return wait("INVALID_TIMESTAMP")
    if not 0<=age<=10:
        return wait("STALE_OR_FUTURE_QUOTE")
    try:
        px=float(price)
        rating=float(score)
    except (ValueError,TypeError,OverflowError):
        return wait("INVALID_METRICS")
    if not (math.isfinite(px) and px>0 and math.isfinite(rating) and 0<=rating<=100):
        return wait("INVALID_METRICS")
    if risk_blocked is True:
        return wait("RISK_BLOCK")
    if not all(x is True for x in (volume_confirmed,sector_confirmed,trend_confirmed)):
        return wait("CONFIRMATION_MISSING")
    if rating<80:
        return wait("LOW_SCORE")
    return {"signal":"BUY","reason":"ALL_FILTERS_VERIFIED",
            "orders_enabled":False,"note":"UNVALIDATED_STRATEGY_SIGNAL"}
