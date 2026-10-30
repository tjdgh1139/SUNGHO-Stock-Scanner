"""Generate an exchange-calendar-backed, short-lived KRX session allowlist.

Research staging only. Does not call KIS, install timers or place orders.
The calendar package is a dependency of the isolated staging environment.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

def build_calendar(*, now_utc=None, horizon_days=7, calendar=None):
    if not 1 <= horizon_days <= 14:
        raise ValueError("horizon out of range")
    if calendar is None:
        import exchange_calendars as xc
        calendar=xc.get_calendar("XKRX")
    now=now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone required")
    today=now.astimezone(ZoneInfo("Asia/Seoul")).date()
    end=today+timedelta(days=horizon_days)
    sessions=calendar.sessions_in_range(today.isoformat(),end.isoformat())
    dates=[str(day.date()) for day in sessions]
    return {"market":"KRX","generated_at_utc":now.astimezone(timezone.utc).isoformat(),
            "valid_through_local_date":end.isoformat(),
            "verified_open_dates":dates,
            "calendar_source":"exchange_calendars:XKRX"}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--horizon-days",type=int,default=7)
    args=parser.parse_args(argv)
    data=build_calendar(horizon_days=args.horizon_days)
    target=Path(args.output)
    if target.exists():
        raise FileExistsError("Refusing to overwrite existing calendar")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":"CREATED","sessions":len(data["verified_open_dates"]),
                      "valid_through":data["valid_through_local_date"]}))

if __name__=="__main__":
    main()
