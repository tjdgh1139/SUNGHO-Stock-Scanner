"""ATLAS paper-only BUY/WAIT/SELL decision orchestration.

Advisory signals, not executions. A missing feed cannot produce an action.
"""
from atlas_candidate_signal_gate import candidate_decision
from atlas_paper_exit_gate import paper_exit_decision

def signal_cycle(*, position_open=False, entry_price=None, stop_price=None,
                 target_price=None, invalidated=False, feed_verified=False,
                 observed_at_utc=None, now=None, price=None, score=None,
                 volume_confirmed=False, sector_confirmed=False,
                 trend_confirmed=False, risk_blocked=False):
    if now is None:
        raise ValueError("now required")
    if position_open is True:
        decision=paper_exit_decision(
            entry_price=entry_price,current_price=price,
            stop_price=stop_price,target_price=target_price,
            feed_verified=feed_verified,observed_at_utc=observed_at_utc,
            now=now,invalidated=invalidated)
    else:
        decision=candidate_decision(
            feed_verified=feed_verified,observed_at_utc=observed_at_utc,
            now=now,price=price,score=score,
            volume_confirmed=volume_confirmed,
            sector_confirmed=sector_confirmed,
            trend_confirmed=trend_confirmed,risk_blocked=risk_blocked)
    return {**decision,"mode":"PAPER_ONLY","real_orders_allowed":False,
            "executed":False}
