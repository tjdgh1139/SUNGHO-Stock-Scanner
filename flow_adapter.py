"""Adapt KIS quote snapshots into conservative ATLAS flow evaluation.

Source timestamps must be explicit ISO-8601 UTC/offset strings; receipt times alone
are not evidence of exchange-time freshness. Foreign/institution flow is NOT inferred
from KIS program trading.
"""
from flow_signals import evaluate_flow


def evaluate_kis_flow(previous, current, *, now, expected_turnover_per_min=None):
    """Use same symbol, market and trading date; fail closed if any are absent."""
    blocked = {"signal": "WAIT", "reason": "unverified_market_identity",
               "turnover_ratio": None}
    try:
        identity = ("코드", "quote_market", "market_date")
        if any(not previous.get(k) or not current.get(k) or previous[k] != current[k]
               for k in identity):
            return blocked
        def adapt(row):
            return {
                "timestamp": row["trade_received_utc"],
                "price": row["현재가"],
                "cumulative_volume": row["누적거래량"],
                "cumulative_turnover": row["누적거래대금"],
                "trade_strength": row["체결강도"],
                "program_net_krw": row["프로그램순매수대금"],
            }
        return evaluate_flow(adapt(previous), adapt(current), now=now,
                             expected_turnover_per_min=expected_turnover_per_min)
    except (KeyError, TypeError, ValueError):
        return blocked
