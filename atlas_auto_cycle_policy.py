"""ATLAS automatic research cycle policy.

Pure scheduler decision logic; no background execution, API access or trades.
The persistent runner must supply exchange-calendar verified session state.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class SessionState:
    market: str
    phase: str  # CLOSED, PREOPEN, REGULAR, AFTERHOURS
    calendar_verified: bool
    feed_healthy: bool

def cycle_actions(session: SessionState, *, outstanding_followups: int) -> dict:
    if session.market not in ("KRX","NYSE","NASDAQ"):
        return {"run":False,"reason":"UNSUPPORTED_MARKET","actions":[]}
    if not session.calendar_verified:
        return {"run":False,"reason":"CALENDAR_UNVERIFIED","actions":[]}
    if outstanding_followups < 0:
        return {"run":False,"reason":"INVALID_FOLLOWUPS","actions":[]}
    # Followups are allowed even when the market is closed, but live scans are not.
    actions=["EVALUATE_PRIOR_SIGNALS"] if outstanding_followups else []
    if session.phase=="CLOSED":
        return {"run":bool(actions),"reason":"CLOSED","actions":actions}
    if session.phase not in ("PREOPEN","REGULAR","AFTERHOURS"):
        return {"run":False,"reason":"UNKNOWN_PHASE","actions":[]}
    if not session.feed_healthy:
        return {"run":bool(actions),"reason":"FEED_UNHEALTHY","actions":actions}
    actions.extend(("COLLECT_QUOTES","CHECK_DATA_QUALITY"))
    if session.phase=="REGULAR":
        actions.append("RESEARCH_CANDIDATES")
    return {"run":True,"reason":"OK","actions":actions}
