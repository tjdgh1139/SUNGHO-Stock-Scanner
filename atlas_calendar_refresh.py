"""Refresh KRX staging calendar atomically without broker requests.

A timer may call this entrypoint independently; it never places orders or
installs a scheduler. Failure preserves the last known-good calendar.
"""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from atlas_krx_calendar_export import build_calendar

def refresh_calendar(path: str, *, now_utc=None, horizon_days=7, calendar=None):
    target=Path(path)
    data=build_calendar(now_utc=now_utc, horizon_days=horizon_days, calendar=calendar)
    target.parent.mkdir(parents=True,exist_ok=True)
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",
                dir=target.parent,prefix=".atlas-calendar-",suffix=".tmp",
                delete=False) as tmp:
            temp_path=tmp.name
            json.dump(data,tmp,ensure_ascii=False,sort_keys=True)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.chmod(temp_path,0o600)
        os.replace(temp_path,target)
        temp_path=None
        return {"status":"REFRESHED","sessions":len(data["verified_open_dates"]),
                "valid_through":data["valid_through_local_date"]}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--horizon-days",type=int,default=7)
    args=parser.parse_args(argv)
    print(json.dumps(refresh_calendar(args.output,horizon_days=args.horizon_days)))

if __name__=="__main__":
    main()
