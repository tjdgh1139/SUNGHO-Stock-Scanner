"""ATLAS staging one-shot scheduler gate.

An external timer may invoke this script; it does NOT install a timer.
Only runs on verified regular KRX sessions and requires a dated exchange
calendar file. Uses a nonblocking process lock to prevent overlap.
No trade orders, no automatic deployments.
"""
import argparse
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from atlas_exchange_session_gate import market_gate

def main(argv=None, *, now_utc=None, collector=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--calendar",required=True)
    parser.add_argument("--lock-file",required=True)
    parser.add_argument("--db",required=True)
    parser.add_argument("--health-db",required=True)
    parser.add_argument("--symbols",nargs="+",required=True)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args(argv)
    try:
        data=json.loads(Path(args.calendar).read_text(encoding="utf-8"))
        if data.get("market")!="KRX" or not isinstance(data.get("verified_open_dates"),list):
            raise ValueError("invalid calendar")
        dates=set(data["verified_open_dates"])
        if any(not isinstance(day,str) for day in dates):
            raise ValueError("invalid dates")
        closes=data.get("verified_early_closes",{})
        if not isinstance(closes,dict):
            raise ValueError("invalid closes")
    except (OSError,ValueError,TypeError) as exc:
        print(json.dumps({"status":"BLOCKED","reason":"CALENDAR_UNAVAILABLE"}))
        return 3
    decision=market_gate("KRX",now_utc or datetime.now(timezone.utc),
                         verified_open_dates=dates,verified_early_closes=closes)
    if not decision["open"]:
        print(json.dumps({"status":"SKIPPED","reason":decision["reason"]}))
        return 0
    if args.dry_run:
        print(json.dumps({"status":"DRY_RUN","reason":"VERIFIED_SESSION"}))
        return 0
    lock_path=Path(args.lock_file)
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status":"SKIPPED","reason":"ALREADY_RUNNING"}))
            return 0
        if collector is None:
            from atlas_kis_health_cli import main as collector
        return collector(["--db",args.db,"--health-db",args.health_db,
                          "--symbols",*args.symbols])

if __name__=="__main__":
    raise SystemExit(main())
