"""Research-only guarded flow evaluation."""
from atlas_intraday_quality import assess_intraday
from flow_adapter import evaluate_kis_flow

def evaluate_safe_flow(previous, current, *, now,
                       expected_turnover_per_min=None):
    for row in (previous, current):
        quote = {
            "received_at_utc": row.get("trade_received_utc"),
            "price": row.get("현재가"),
            "volume": row.get("누적거래량"),
            "turnover": row.get("누적거래대금"),
            "freshness": row.get("freshness"),
        }
        quality = assess_intraday(quote, now_utc=now.isoformat() if hasattr(now, "isoformat") else now)
        if not quality["eligible"]:
            return {"signal": "WAIT",
                    "reason": quality["reason"],
                    "quality_blocked": True}

    return evaluate_kis_flow(
        previous, current, now=now,
        expected_turnover_per_min=expected_turnover_per_min
    )
