"""Fail-closed decision for a provider rate-limit event.

This module is a pure policy. It does not execute requests, retry, or
change the running KIS collector. Rate-limit errors must be identified
by an authenticated adapter, not guessed from exception text.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class RateLimitDecision:
    stop_cycle: bool
    retry_now: bool
    reason: str

def decide_rate_limit(*, http_status=None, kis_code=None):
    if http_status == 429:
        return RateLimitDecision(True,False,"HTTP_429_STOP_CYCLE")
    if kis_code is not None and not isinstance(kis_code,str):
        return RateLimitDecision(True,False,"INVALID_PROVIDER_CODE")
    if http_status in (401,403):
        return RateLimitDecision(True,False,"AUTH_FAILURE_STOP_CYCLE")
    if http_status is not None and (not isinstance(http_status,int) or isinstance(http_status,bool) or not 100<=http_status<=599):
        return RateLimitDecision(True,False,"INVALID_HTTP_STATUS")
    return RateLimitDecision(False,False,"NO_CONFIRMED_RATE_LIMIT")
