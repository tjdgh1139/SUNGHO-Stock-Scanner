"""Pure watchdog for a future always-on ATLAS paper-only collector.

This module never opens sockets, places orders, or manufactures price data.
The collector must pass authenticated feed metadata and heartbeat timestamps.
"""
from datetime import datetime, timezone
import math

MAX_HEARTBEAT_AGE_SECONDS = 15
MAX_TRADE_AGE_SECONDS = 10


def _age_seconds(value, now):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        age = (now - stamp.astimezone(timezone.utc)).total_seconds()
        return age if math.isfinite(age) and age >= 0 else None
    except (ValueError, OverflowError):
        return None


def collector_health(*, connected, heartbeat_utc, latest_trade_utc,
                     verified_symbols, now=None):
    """Fail closed: connected does not imply a usable live trade feed."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    heartbeat_age = _age_seconds(heartbeat_utc, now)
    trade_age = _age_seconds(latest_trade_utc, now)
    if not connected:
        status = "DISCONNECTED"
    elif heartbeat_age is None or heartbeat_age > MAX_HEARTBEAT_AGE_SECONDS:
        status = "STALE_HEARTBEAT"
    elif not isinstance(verified_symbols, int) or isinstance(verified_symbols, bool) or verified_symbols <= 0:
        status = "NO_VERIFIED_SYMBOLS"
    elif trade_age is None or trade_age > MAX_TRADE_AGE_SECONDS:
        status = "STALE_TRADES"
    else:
        status = "LIVE_VERIFIED"
    return {
        "status": status,
        "paper_signal_allowed": status == "LIVE_VERIFIED",
        "heartbeat_age_seconds": heartbeat_age,
        "trade_age_seconds": trade_age,
        "verified_symbols": verified_symbols if isinstance(verified_symbols, int) and not isinstance(verified_symbols, bool) and verified_symbols >= 0 else 0,
        "real_orders_allowed": False,
    }
