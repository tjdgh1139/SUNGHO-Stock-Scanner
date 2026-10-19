"""ATLAS offline market-session scheduler (pure and order-free).

Schedules only decide when to observe. They never imply live feed availability.
US exchange holidays and special sessions must be provided by a verified calendar.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

KST=ZoneInfo("Asia/Seoul")
NY=ZoneInfo("America/New_York")

def scheduled_sessions(now, *, kr_holiday=False, us_holiday=False):
    if now.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    kr=now.astimezone(KST)
    us=now.astimezone(NY)
    kr_weekday=kr.weekday()<5 and not kr_holiday
    us_weekday=us.weekday()<5 and not us_holiday
    kr_clock=kr.time()
    us_clock=us.time()
    nxt=kr_weekday and time(8,0)<=kr_clock<time(20,0)
    krx=kr_weekday and time(9,0)<=kr_clock<time(15,30)
    us_regular=us_weekday and time(9,30)<=us_clock<time(16,0)
    return {"kr_date":kr.date().isoformat(),"us_date":us.date().isoformat(),
            "nxt_window":nxt,"krx_window":krx,"us_regular_window":us_regular,
            "kr_holiday_verified":bool(kr_holiday),
            "us_holiday_verified":bool(us_holiday),
            "real_orders_allowed":False,
            "note":"Time windows only; require independent exchange-calendar and authenticated feed checks"}
