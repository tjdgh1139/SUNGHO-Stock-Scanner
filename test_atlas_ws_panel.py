from datetime import datetime, timedelta, timezone
from atlas_ws_panel import live_state

NOW=datetime(2026,10,16,1,0,tzinfo=timezone.utc)

def row():
    stamp=(NOW-timedelta(seconds=3)).isoformat()
    return {"quote_market":"J","market_date":"20261016",
            "trade_received_utc":stamp,"book_received_utc":stamp,
            "program_received_utc":stamp,"현재가":120000}

def test_complete_recent_live():
    assert live_state(row(),True,NOW)=="실시간 수신 확인"

def test_missing_program_blocks_live():
    r=row();r.pop("program_received_utc")
    assert live_state(r,True,NOW)!="실시간 수신 확인"

def test_disconnected_blocks_live():
    assert live_state(row(),False,NOW)!="실시간 수신 확인"

def test_stale_book_blocks_live():
    r=row();r["book_received_utc"]=(NOW-timedelta(seconds=12)).isoformat()
    assert live_state(r,True,NOW)!="실시간 수신 확인"

def test_future_timestamp_blocks_live():
    r=row();r["trade_received_utc"]=(NOW+timedelta(seconds=20)).isoformat()
    assert live_state(r,True,NOW)!="실시간 수신 확인"

def test_mixed_market_blocks_live():
    r=row();r["quote_market"]="NX"
    assert live_state(r,True,NOW)!="실시간 수신 확인"

def test_previous_day_blocks_live():
    r=row();r["market_date"]="20261015"
    assert live_state(r,True,NOW)!="실시간 수신 확인"
