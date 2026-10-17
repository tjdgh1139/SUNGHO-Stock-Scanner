from datetime import datetime,timedelta,timezone
from atlas_preopen_monitor import freeze_candidates,minute_after_open,minute_record,assess_candidate

PRE=datetime(2026,10,15,23,55,tzinfo=timezone.utc)
OPEN=datetime(2026,10,16,0,0,tzinfo=timezone.utc)

def candidate():
    return {"코드":"000660","종목":"하이닉스","점수":90,
            "매수하단":100,"매수상단":105,"손절가":96,"1차목표":115}

def test_freeze_only_preopen():
    r=freeze_candidates([candidate()],"KR",now=PRE)
    assert r["session_date"]=="20261016"
    assert len(r["candidates"])==1 and r["candidates"][0]["stop"]==96
    assert freeze_candidates([candidate()],"KR",now=OPEN) is None

def test_opening_minutes_1_through_5():
    for m in range(5):
        assert minute_after_open(OPEN+timedelta(minutes=m),"KR")==m+1
    assert minute_after_open(OPEN+timedelta(minutes=5),"KR") is None

def test_us_opening_minutes():
    now=datetime(2026,10,16,13,30,tzinfo=timezone.utc)
    assert minute_after_open(now,"US")==1

def test_no_invented_levels():
    r=freeze_candidates([{"코드":"005930","종목":"삼전","점수":80}],"KR",now=PRE)
    assert r["candidates"][0]["stop"] is None

def quote(price=102,stamp=None):
    return {"현재가":price,"quote_market":"J",
            "quote_received_utc":(stamp or OPEN+timedelta(seconds=30)).isoformat()}

def test_stop_trigger_is_not_order():
    r=freeze_candidates([candidate()],"KR",now=PRE)
    x=assess_candidate(r["candidates"][0],quote(95),now=OPEN+timedelta(seconds=30))
    assert "손절 기준 이탈" in x["status"]

def test_target_trigger():
    r=freeze_candidates([candidate()],"KR",now=PRE)
    x=assess_candidate(r["candidates"][0],quote(116),now=OPEN+timedelta(seconds=30))
    assert "익절 검토" in x["status"]

def test_stale_price_fails_closed():
    r=freeze_candidates([candidate()],"KR",now=PRE)
    x=assess_candidate(r["candidates"][0],quote(120,OPEN-timedelta(minutes=5)),now=OPEN+timedelta(seconds=30))
    assert x["price"] is None and "WAIT" in x["status"]

def test_wrong_market_fails_closed():
    r=freeze_candidates([candidate()],"KR",now=PRE)
    q=quote();q["quote_market"]="NX"
    assert assess_candidate(r["candidates"][0],q,now=OPEN+timedelta(seconds=30))["price"] is None

def test_minute_record_requires_matching_day():
    r=freeze_candidates([candidate()],"KR",now=PRE)
    assert minute_record(r,{"000660":quote()},now=OPEN+timedelta(days=1)) is None
    result=minute_record(r,{"000660":quote()},now=OPEN+timedelta(seconds=30))
    assert result["minute"]==1 and len(result["rows"])==1
