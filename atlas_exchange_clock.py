"""Research-only KRX exchange clock validation."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

def validate_exchange_clock(hhmmss, received_utc, market_date):
    try:
        if not isinstance(hhmmss, str) or len(hhmmss) != 6 or not hhmmss.isascii() or not hhmmss.isdigit():
            raise ValueError("invalid clock format")
        if not isinstance(market_date, str) or len(market_date) != 8 or not market_date.isascii() or not market_date.isdigit():
            raise ValueError("invalid market date")
        received = datetime.fromisoformat(received_utc.replace("Z", "+00:00"))
        if received.tzinfo is None:
            raise ValueError("timezone missing")
        exchange = datetime.strptime(market_date + hhmmss, "%Y%m%d%H%M%S").replace(tzinfo=KST).astimezone(timezone.utc)
        lag = (received.astimezone(timezone.utc) - exchange).total_seconds()
        if lag < -5 or lag > 120:
            raise ValueError("clock lag outside limits")
        return {"valid": True, "exchange_utc": exchange.isoformat(), "lag_seconds": lag}
    except (ValueError, TypeError, AttributeError, OverflowError):
        return {"valid": False, "exchange_utc": None, "lag_seconds": None}
