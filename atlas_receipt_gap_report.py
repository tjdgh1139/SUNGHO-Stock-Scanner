"""Read-only KRX receipt interval diagnostics; no exchange-time claims."""
import argparse
import json
import sqlite3
from datetime import datetime, time
from zoneinfo import ZoneInfo
from pathlib import Path

def receipt_gaps(db_path, *, market="KRX", threshold_seconds=420, regular_session_only=False, calendar=None):
    if threshold_seconds<=0:
        raise ValueError("threshold must be positive")
    if calendar is not None and not regular_session_only:
        raise ValueError("calendar requires regular-session-only")
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
                if regular_session_only:
                    local=t.astimezone(ZoneInfo("Asia/Seoul"))
                    # Clock window alone is insufficient to verify holidays.
                    # Restrict comparisons to same weekday and regular hours.
                    if (local.weekday()>=5 or
                        (calendar is not None and not calendar.is_session(local.date().isoformat())) or
                        not (time(9,0)<=local.time()<time(15,30))):
                        prev=None
                        continue
                    if prev is not None and prev.astimezone(ZoneInfo("Asia/Seoul")).date()!=local.date():
                        prev=None
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
          "note":("XKRX calendar-verified regular-session same-day gaps; not an exchange-time SLA." if calendar is not None else "Weekday KST 09:00-15:30 same-day gaps only; holidays not verified." if regular_session_only else "Includes overnight/closed-market gaps; not a market-hours SLA.")})
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True)
    p.add_argument("--threshold-seconds",type=float,default=420)
    p.add_argument("--regular-session-only",action="store_true")
    p.add_argument("--verify-krx-calendar",action="store_true")
    args=p.parse_args(argv)
    if args.verify_krx_calendar and not args.regular_session_only:
        p.error("--verify-krx-calendar requires --regular-session-only")
    calendar=None
    if args.verify_krx_calendar:
        import exchange_calendars as xc
        calendar=xc.get_calendar("XKRX")
    print(json.dumps(receipt_gaps(args.db,threshold_seconds=args.threshold_seconds,regular_session_only=args.regular_session_only,calendar=calendar)))
if __name__=="__main__":
    main()
