"""ATLAS read-only collection cycle coordinator.

Coordinates one explicit collection attempt, engine health evaluation and
bounded retry recommendation. It never schedules itself or places orders.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from atlas_market_collection import collect_cycle
from atlas_engine_health import evaluate_cycle
from atlas_retry_policy import retry_policy
from atlas_collector_heartbeat import save_heartbeat

@dataclass(frozen=True)
class CycleOutcome:
    health: object
    retry: object
    result: object

def run_cycle(db_path, symbols, provider, *, received_at_utc=None,
              consecutive_failures=0, last_status_code=None,
              heartbeat_db_path=None, market='KRX', heartbeat_at_utc=None,
              stop_on=()):
    universe=list(dict.fromkeys(symbols))
    result=collect_cycle(db_path,universe,provider,received_at_utc=received_at_utc,
                         stop_on=stop_on)
    health=evaluate_cycle(result,expected=len(universe))
    if health.state=="HEALTHY":
        retry=None
    else:
        retry=retry_policy(consecutive_failures=max(1,consecutive_failures+1),
                           status_code=last_status_code)
    if heartbeat_db_path is not None:
        stamp = heartbeat_at_utc or datetime.now(timezone.utc).isoformat()
        try:
            save_heartbeat(heartbeat_db_path, market=market,
                           observed_at_utc=stamp, state=health.state,
                           reason=health.reason, attempted=health.attempted,
                           stored=health.stored, failed=health.failed)
        except Exception as exc:
            # Never report HEALTHY if the operational journal cannot persist.
            from atlas_engine_health import EngineHealth
            health=EngineHealth('HALTED','HEARTBEAT_PERSISTENCE_FAILED',
                                health.attempted,health.stored,health.duplicates,health.failed)
            retry=None
    return CycleOutcome(health=health,retry=retry,result=result)
