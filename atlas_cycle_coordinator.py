"""ATLAS read-only collection cycle coordinator.

Coordinates one explicit collection attempt, engine health evaluation and
bounded retry recommendation. It never schedules itself or places orders.
"""
from dataclasses import dataclass
from atlas_market_collection import collect_cycle
from atlas_engine_health import evaluate_cycle
from atlas_retry_policy import retry_policy

@dataclass(frozen=True)
class CycleOutcome:
    health: object
    retry: object
    result: object

def run_cycle(db_path, symbols, provider, *, received_at_utc=None,
              consecutive_failures=0, last_status_code=None):
    universe=list(dict.fromkeys(symbols))
    result=collect_cycle(db_path,universe,provider,received_at_utc=received_at_utc)
    health=evaluate_cycle(result,expected=len(universe))
    if health.state=="HEALTHY":
        retry=None
    else:
        retry=retry_policy(consecutive_failures=max(1,consecutive_failures+1),
                           status_code=last_status_code)
    return CycleOutcome(health=health,retry=retry,result=result)
