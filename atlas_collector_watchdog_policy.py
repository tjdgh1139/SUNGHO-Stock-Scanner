"""ATLAS read-only collector watchdog decisions.

Stateless policy suitable for a persistent runner. Never starts jobs,
changes deployment, places orders, or prints secrets.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class WatchdogDecision:
    action: str
    reason: str

def decide_watchdog(*, consecutive_failures: int, last_success_age_seconds: float | None,
                    market_open: bool, max_failures: int = 5,
                    max_stale_seconds: int = 300) -> WatchdogDecision:
    if consecutive_failures < 0 or max_failures < 1 or max_stale_seconds <= 0:
        return WatchdogDecision("HALT","INVALID_CONFIGURATION")
    if consecutive_failures >= max_failures:
        return WatchdogDecision("HALT","CIRCUIT_OPEN")
    if not market_open:
        return WatchdogDecision("WAIT","MARKET_CLOSED")
    if last_success_age_seconds is None:
        return WatchdogDecision("ALERT","NO_SUCCESS_RECORDED")
    if last_success_age_seconds < 0:
        return WatchdogDecision("HALT","CLOCK_ANOMALY")
    if last_success_age_seconds > max_stale_seconds:
        return WatchdogDecision("ALERT","STALE_COLLECTION")
    return WatchdogDecision("CONTINUE","HEALTHY")
