"""Research-only intraday eligibility gate."""
import math
from atlas_quote_quality import assess_quote

def assess_intraday(quote, *, now_utc):
    base = assess_quote(quote, now_utc=now_utc)
    if not base["usable"]:
        return {"eligible": False, "action": "WAIT",
                "reason": base["reason"]}

    if quote.get("freshness") != "VERIFIED_EXCHANGE_TIME":
        return {"eligible": False, "action": "WAIT",
                "reason": "UNVERIFIED_EXCHANGE_TIME"}

    for field in ("price", "volume", "turnover"):
        try:
            value = float(quote[field])
            if not math.isfinite(value) or value <= 0:
                raise ValueError("invalid")
        except (KeyError, TypeError, ValueError, OverflowError):
            return {"eligible": False, "action": "WAIT",
                    "reason": "INVALID_" + field.upper()}

    return {"eligible": True, "action": "EVALUATE",
            "reason": "QUALITY_OK"}
