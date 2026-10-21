"""Research-only WebSocket quote quality annotation."""
from atlas_exchange_clock import validate_exchange_clock

def annotate_ws_quote(row, *, connected=False, subscribed=False):
    result = dict(row)
    result["exchange_clock_valid"] = False
    result["exchange_utc"] = None
    result["exchange_lag_seconds"] = None
    result["signal_eligible"] = False

    if not connected or not subscribed:
        result["quality_reason"] = "WS_NOT_CONFIRMED"
        return result

    if result.get("quote_market") != "J":
        result["quality_reason"] = "MARKET_NOT_SUPPORTED"
        return result

    check = validate_exchange_clock(
        result.get("체결시간"),
        result.get("trade_received_utc"),
        result.get("market_date"),
    )

    result["exchange_clock_valid"] = check["valid"]
    result["exchange_utc"] = check["exchange_utc"]
    result["exchange_lag_seconds"] = check["lag_seconds"]
    result["quality_reason"] = (
        "CLOCK_VALID_SOURCE_UNVERIFIED"
        if check["valid"] else "INVALID_EXCHANGE_CLOCK"
    )
    return result
