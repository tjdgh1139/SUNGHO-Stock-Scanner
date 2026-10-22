"""Read-only KRX receipt interval diagnostics; no exchange-time claims."""
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

def receipt_gaps(db_path, *, market="KRX", threshold_seconds=420):
    if threshold_seconds<=0:
        raise ValueError("threshold must be positive")
    with sqlite3.connect("file:"+str(Path(db_path).resolve())+"?mode=ro",uri=True) as db:
        rows=db.execute("""SELECT symbol,received_at_utc FROM market_quotes
          WHERE market=? ORDER BY symbol,received_at_utc,id""",(market,)).fetchall()
    grouped={}
    for symbol,stamp in rows:
        grouped.setdefault(symbol,[]).append(stamp)
    report=[]
    for symbol,stamps in grouped.items():
        gaps=[]
        invalid=0
        prev=None
        for stamp in stamps:
            try:
                t=datetime.fromisoformat(stamp.replace("Z","+00:00"))
                if t.tzinfo is None:
                    raise ValueError("timezone missing")
                if prev is not None:
                    gap=(t-prev).total_seconds()
                    if gap>=0:
                        gaps.append(gap)
                    else:
                        invalid+=1
                prev=t
            except (ValueError,TypeError,AttributeError):
                invalid+=1
                prev=None
        report.append({"symbol":symbol,"records":len(stamps),
          "max_gap_seconds":round(max(gaps),2) if gaps else None,
          "gaps_over_threshold":sum(g>threshold_seconds for g in gaps),
          "invalid_timestamps":invalid,
          "note":"Includes overnight/closed-market gaps; not a market-hours SLA."})
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True)
    p.add_argument("--threshold-seconds",type=float,default=420)
    args=p.parse_args(argv)
    print(json.dumps(receipt_gaps(args.db,threshold_seconds=args.threshold_seconds)))
if __name__=="__main__":
    main()
