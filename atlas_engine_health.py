"""ATLAS research collector engine health policy.

Fail closed on absent/invalid coverage. This module is pure, requires no
credentials and never initiates orders or background processes.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class EngineHealth:
    state: str
    reason: str
    attempted: int
    stored: int
    duplicates: int
    failed: int

def evaluate_cycle(cycle, *, expected: int) -> EngineHealth:
    try:
        raw = (cycle.attempted, cycle.stored, cycle.duplicates)
        if any(isinstance(v, bool) or not isinstance(v, int) for v in raw):
            raise ValueError("noninteger counters")
        attempted, stored, duplicates = raw
        failed = len(cycle.failed)
    except (AttributeError, TypeError, ValueError):
        return EngineHealth("HALTED", "INVALID_COUNTERS", 0, 0, 0, 0)
    if expected<=0:
        return EngineHealth("HALTED","EMPTY_UNIVERSE",attempted,stored,duplicates,failed)
    if attempted!=expected:
        return EngineHealth("DEGRADED","UNIVERSE_COUNT_MISMATCH",attempted,stored,duplicates,failed)
    if min(attempted,stored,duplicates,failed)<0 or stored+duplicates+failed!=attempted:
        return EngineHealth("HALTED","INCONSISTENT_COUNTS",attempted,stored,duplicates,failed)
    if failed:
        return EngineHealth("DEGRADED","PROVIDER_FAILURE",attempted,stored,duplicates,failed)
    if stored==0 and duplicates==expected:
        return EngineHealth("DEGRADED","NO_NEW_OBSERVATIONS",attempted,stored,duplicates,failed)
    return EngineHealth("HEALTHY","OK",attempted,stored,duplicates,failed)
