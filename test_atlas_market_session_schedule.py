from datetime import datetime, timezone
from atlas_market_session_schedule import scheduled_sessions

def test_nxt_open_before_krx():
    r=scheduled_sessions(datetime(2026,10,18,23,0,tzinfo=timezone.utc))
    assert r["nxt_window"] and not r["krx_window"]

def test_krx_open_and_nxt_open():
    r=scheduled_sessions(datetime(2026,10,19,0,5,tzinfo=timezone.utc))
    assert r["nxt_window"] and r["krx_window"]

def test_weekend_closed():
    r=scheduled_sessions(datetime(2026,10,17,0,0,tzinfo=timezone.utc))
    assert not r["nxt_window"] and not r["krx_window"]

def test_holiday_closes_exchange():
    r=scheduled_sessions(datetime(2026,10,19,0,5,tzinfo=timezone.utc),kr_holiday=True)
    assert not r["nxt_window"] and not r["krx_window"]

def test_no_real_orders():
    r=scheduled_sessions(datetime(2026,10,19,0,5,tzinfo=timezone.utc))
    assert r["real_orders_allowed"] is False
