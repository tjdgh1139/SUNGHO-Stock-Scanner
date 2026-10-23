"""ATLAS bounded retry policy for unattended read-only data collection.

Pure decision function; never executes requests or places orders.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay_seconds: int
    reason: str

def retry_policy(*, consecutive_failures: int, status_code: int | None,
                 max_failures: int = 5) -> RetryDecision:
    if consecutive_failures < 1 or max_failures < 1:
        raise ValueError("invalid retry counters")
    if status_code in (400,401,403):
        return RetryDecision(False,0,"AUTH_OR_REQUEST_REQUIRES_REVIEW")
    if consecutive_failures >= max_failures:
        return RetryDecision(False,0,"CIRCUIT_OPEN")
    if status_code == 429 or status_code is None or 500 <= status_code <= 599:
        delay=min(300,2 ** min(consecutive_failures,8))
        return RetryDecision(True,delay,"BOUNDED_BACKOFF")
    return RetryDecision(False,0,"NON_RETRYABLE")
