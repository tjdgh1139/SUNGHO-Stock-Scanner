"""ATLAS NXT opening radar: deterministic observation-only risk assessment.

No price forecasts, orders, or invented support levels. A NXT observation
never proves KRX demand or a corporate buyback execution.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

KST = ZoneInfo("Asia/Seoul")
MAX_AGE_SECONDS = 10

def _stamp(value):
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except (ValueError, OverflowError):
        return None

def opening_radar(*, price, observed_at_utc, session_date, verified,
                  previous_close, risk_floor=None, now=None):
    """Classify NXT early trading without conflating it with KRX flow."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware now required")
    now = now.astimezone(timezone.utc)
    stamp = _stamp(observed_at_utc)
    try:
        px, close = float(price), float(previous_close)
        floor = float(risk_floor) if risk_floor is not None else None
    except (ValueError, TypeError):
        px = close = float("nan")
        floor = None
    fresh = (stamp is not None and 0 <= (now-stamp).total_seconds() <= MAX_AGE_SECONDS)
    valid = (verified is True and fresh
             and session_date == now.astimezone(KST).strftime("%Y%m%d")
             and math.isfinite(px) and px > 0
             and math.isfinite(close) and close > 0)
    if not valid:
        return {"status":"UNVERIFIED","change_pct":None,
                "floor_breached":None,"signal":"WAIT",
                "krx_confirmation":False,"buyback_verified":False}
    change = (px / close - 1) * 100
    breached = (px < floor if floor is not None and math.isfinite(floor) and floor > 0
                else None)
    return {"status":"NXT_OBSERVED","change_pct":round(change,3),
            "floor_breached":breached,"signal":"WAIT",
            "krx_confirmation":False,"buyback_verified":False}
