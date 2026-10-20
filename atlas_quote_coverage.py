"""ATLAS quote coverage report for research-only scans.

No claim of full market coverage when symbols or observations are missing.
"""
import sqlite3
from pathlib import Path
from atlas_market_quote_store import SCHEMA as QUOTE_SCHEMA

def coverage_report(db_path: str, market: str, expected_symbols: list[str],
                    start_utc: str, end_utc: str) -> dict:
    symbols=list(dict.fromkeys(expected_symbols))
    if not start_utc < end_utc:
        raise ValueError("invalid time window")
    if not symbols:
        return {"market":market,"expected":0,"observed":0,
                "coverage_pct":None,"missing":[],"observations":0}
    if not Path(db_path).exists():
        return {"market":market,"expected":len(symbols),"observed":0,
                "coverage_pct":0.0,"missing":symbols,"observations":0}
    with sqlite3.connect(db_path) as con:
        con.executescript(QUOTE_SCHEMA)
        found=con.execute(
            """SELECT symbol,COUNT(*) FROM market_quotes
               WHERE market=? AND received_at_utc>=? AND received_at_utc<?
               GROUP BY symbol""",(market,start_utc,end_utc)).fetchall()
    counts={s:n for s,n in found}
    observed=[s for s in symbols if counts.get(s,0)>0]
    return {"market":market,"expected":len(symbols),"observed":len(observed),
            "coverage_pct":round(100*len(observed)/len(symbols),2),
            "missing":[s for s in symbols if s not in observed],
            "observations":sum(counts.get(s,0) for s in symbols)}
