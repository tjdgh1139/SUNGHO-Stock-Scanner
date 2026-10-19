"""ATLAS collector integration gate: calendar + authenticated feed + durable health.

This module connects existing pure components without creating broker orders.
It does not claim that the KIS adapter or a 24/7 server is deployed.
"""
from datetime import datetime, timezone
from atlas_market_session_schedule import scheduled_sessions
from atlas_collector_runner import poll_once

def market_poll(source, sink, *, venue, now=None, kr_holiday=False,
                us_holiday=False, calendar_verified=False):
    now=now or datetime.now(timezone.utc)
    windows=scheduled_sessions(now,kr_holiday=kr_holiday,us_holiday=us_holiday)
    names={"NXT":"nxt_window","KRX":"krx_window","US":"us_regular_window"}
    if venue not in names:
        raise ValueError("unsupported venue")
    permitted=(calendar_verified is True and windows[names[venue]])
    if not permitted:
        record={"event":"COLLECTOR_HEALTH","observed_at_utc":now.isoformat(),
                "status":"MARKET_CLOSED_OR_CALENDAR_UNVERIFIED",
                "paper_signal_allowed":False,"real_orders_allowed":False,
                "venue":venue}
        sink(record)
        return record
    result=poll_once(source,sink,now=now)
    result["venue"]=venue
    return result
