"""Conservative intraday flow confirmation from consecutive, timestamped snapshots.

No trading orders. The caller must supply a *same-clock-time* turnover baseline.
Missing or stale data never produces a BUY_CANDIDATE signal.
"""
from datetime import datetime, timezone


def _utc(value):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp required")
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result.astimezone(timezone.utc)


def evaluate_flow(previous, current, *, now, expected_turnover_per_min=None):
    """Evaluate two cumulative KRW snapshots.

    Required keys: timestamp, price, cumulative_volume, cumulative_turnover,
    trade_strength, program_net_krw. All monetary values are in KRW.
    Returns a diagnostic dict; never an order instruction.
    """
    result = {"signal": "WAIT", "reason": "unverified", "turnover_ratio": None}
    try:
        t0, t1, clock = (_utc(previous["timestamp"]), _utc(current["timestamp"]), _utc(now))
        elapsed = (t1 - t0).total_seconds()
        age = (clock - t1).total_seconds()
        if not 10 <= elapsed <= 300 or not 0 <= age <= 120:
            return {**result, "reason": "stale_or_invalid_timestamps"}
        p0, p1 = float(previous["price"]), float(current["price"])
        v0, v1 = float(previous["cumulative_volume"]), float(current["cumulative_volume"])
        a0, a1 = float(previous["cumulative_turnover"]), float(current["cumulative_turnover"])
        strength = float(current["trade_strength"])
        program0, program1 = float(previous["program_net_krw"]), float(current["program_net_krw"])
        if not all(map(lambda x: x == x and abs(x) != float("inf"), [p0,p1,v0,v1,a0,a1,strength,program0,program1])):
            return {**result, "reason": "non_finite_values"}
        if p0 <= 0 or p1 <= 0 or v0 < 0 or a0 < 0 or v1 < v0 or a1 < a0:
            return {**result, "reason": "invalid_or_reset_cumulative_values"}
        rate = (a1 - a0) * 60 / elapsed
        move_pct = (p1 / p0 - 1) * 100
        if expected_turnover_per_min is None:
            return {**result, "reason": "missing_same_time_baseline", "turnover_per_min": rate}
        baseline = float(expected_turnover_per_min)
        if not 0 < baseline < float("inf"):
            return {**result, "reason": "invalid_baseline"}
        ratio = rate / baseline
        diagnostics = {"turnover_ratio": round(ratio, 3), "turnover_per_min": rate,
                       "price_change_pct": round(move_pct, 3),
                       "program_net_change_krw": program1 - program0}
        if ratio >= 1.8 and move_pct >= 0.3 and strength >= 110 and program1 >= program0:
            return {**result, **diagnostics, "signal": "BUY_CANDIDATE",
                    "reason": "volume_price_strength_program_confirmed"}
        return {**result, **diagnostics, "signal": "WATCH", "reason": "confirmation_incomplete"}
    except (ValueError, TypeError, KeyError, OverflowError):
        return {**result, "reason": "invalid_snapshot"}
