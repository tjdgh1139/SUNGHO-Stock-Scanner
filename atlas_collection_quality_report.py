"""Read-only operational summary; not broker API request counts or trading advice."""
import argparse
import json
import sqlite3
from pathlib import Path

def _read(db_path, query, params=()):
    with sqlite3.connect("file:"+str(Path(db_path).resolve())+"?mode=ro",uri=True) as db:
        return db.execute(query,params).fetchall()

def summarize(quote_db, health_db, audit_db):
    counts=_read(quote_db,"SELECT symbol,COUNT(*),MAX(received_at_utc) FROM market_quotes WHERE market='KRX' GROUP BY symbol ORDER BY symbol")
    health=_read(health_db,"SELECT state,COUNT(*),SUM(attempted),SUM(stored),SUM(failed) FROM collector_heartbeat WHERE market='KRX' GROUP BY state ORDER BY state")
    blocks=_read(audit_db,"SELECT symbol,status,reason,COUNT(*) FROM quote_quality_audit WHERE market='KRX' GROUP BY symbol,status,reason ORDER BY symbol,status,reason")
    return {"quotes":[{"symbol":s,"records":n,"latest_received_utc":t} for s,n,t in counts],
            "cycles":[{"state":s,"cycles":n,"attempted":a,"stored":b,"failed":f} for s,n,a,b,f in health],
            "quality":[{"symbol":s,"status":st,"reason":r,"records":n} for s,st,r,n in blocks],
            "caveat":"Counts are archived observations, not API call counts; no verified exchange-time trade eligibility."}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True)
    p.add_argument("--health-db",required=True)
    p.add_argument("--audit-db",required=True)
    a=p.parse_args(argv)
    print(json.dumps(summarize(a.db,a.health_db,a.audit_db),ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
