"""ATLAS data quality gate for paper research signals.

This module does not make trading decisions or place orders.
Rejects stale/missing data, inadequate universe coverage, and failed
provider collections before any downstream research scoring.
"""
from atlas_quote_quality import assess_quote

def assess_scan_readiness(*, coverage: dict, latest_quotes: dict,
                          now_utc: str, min_coverage_pct: float = 95,
                          max_quote_age_seconds: int = 120,
                          expected_symbols: list[str] | None = None) -> dict:
    if not 0 <= min_coverage_pct <= 100:
        raise ValueError("invalid coverage threshold")
    expected=coverage.get("expected")
    ratio=coverage.get("coverage_pct")
    if not isinstance(expected,int) or expected <= 0:
        return {"ready":False,"reason":"EMPTY_UNIVERSE"}
    if ratio is None or ratio < min_coverage_pct:
        return {"ready":False,"reason":"INSUFFICIENT_COVERAGE",
                "coverage_pct":ratio}
    if expected_symbols is not None:
        universe=set(expected_symbols)
        if len(universe) != expected or not universe:
            return {"ready":False,"reason":"UNIVERSE_MISMATCH"}
        missing=sorted(universe-set(latest_quotes))
        if missing:
            return {"ready":False,"reason":"INCOMPLETE_QUOTE_SET","missing":missing}
        extras=sorted(set(latest_quotes)-universe)
        if extras:
            return {"ready":False,"reason":"UNEXPECTED_SYMBOLS","symbols":extras}
    failures={}
    for symbol,quote in latest_quotes.items():
        quality=assess_quote(quote,now_utc=now_utc,
                             max_age_seconds=max_quote_age_seconds)
        if not quality["usable"]:
            failures[symbol]=quality["reason"]
    if failures:
        return {"ready":False,"reason":"UNUSABLE_QUOTES","failed_symbols":failures}
    if len(latest_quotes) != expected:
        return {"ready":False,"reason":"INCOMPLETE_QUOTE_SET"}
    return {"ready":True,"reason":"OK","coverage_pct":ratio}
