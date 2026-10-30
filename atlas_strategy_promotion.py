"""ATLAS paper-research promotion gate for candidate strategy versions.

No autonomous code deployment or trading. Requires evidence from independent
out-of-sample paper tests before a candidate may be considered for review.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class StrategyEvidence:
    observations: int
    net_return_pct: float
    max_drawdown_pct: float
    data_coverage_pct: float
    test_passed: bool
    out_of_sample: bool

def evaluate_candidate(candidate: StrategyEvidence, baseline: StrategyEvidence,
                       *, min_observations: int = 100,
                       min_coverage_pct: float = 95) -> dict:
    for name, item in (("candidate",candidate),("baseline",baseline)):
        if item.observations < min_observations:
            return {"eligible":False,"reason":f"{name.upper()}_INSUFFICIENT_SAMPLE"}
        if item.data_coverage_pct < min_coverage_pct:
            return {"eligible":False,"reason":f"{name.upper()}_LOW_COVERAGE"}
        if not item.test_passed or not item.out_of_sample:
            return {"eligible":False,"reason":f"{name.upper()}_UNVERIFIED"}
        if item.max_drawdown_pct < 0:
            return {"eligible":False,"reason":f"{name.upper()}_INVALID_DRAWDOWN"}
    if candidate.net_return_pct <= baseline.net_return_pct:
        return {"eligible":False,"reason":"NO_NET_RETURN_IMPROVEMENT"}
    if candidate.max_drawdown_pct > baseline.max_drawdown_pct:
        return {"eligible":False,"reason":"DRAWDOWN_WORSE"}
    return {"eligible":True,"reason":"REVIEW_ELIGIBLE_NOT_DEPLOYED"}
