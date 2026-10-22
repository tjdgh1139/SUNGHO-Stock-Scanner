"""Offline request-cycle duration estimate; not a broker rate-limit approval."""
import math
def estimate_cycle(symbol_count, *, minimum_interval_seconds=0.5,
                   response_seconds=0.0, timeout_seconds=8.0):
    if type(symbol_count) is not int or not 1<=symbol_count<=100:
        raise ValueError("invalid symbol count")
    for value in (minimum_interval_seconds,response_seconds,timeout_seconds):
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):
            raise ValueError("invalid timing")
    if minimum_interval_seconds<=0 or response_seconds<0 or timeout_seconds<=0:
        raise ValueError("invalid timing")
    # Requests are sequential; next request starts after response and pacing.
    typical=symbol_count*response_seconds+(symbol_count-1)*max(0,minimum_interval_seconds-response_seconds)
    worst=symbol_count*timeout_seconds+(symbol_count-1)*max(0,minimum_interval_seconds-timeout_seconds)
    return {"symbols":symbol_count,"estimated_seconds":round(typical,2),
            "timeout_bound_seconds":round(worst,2),
            "safe_to_expand":False,
            "note":"No KIS rate-limit verification; token overhead, scheduling, retries and external delays excluded."}
