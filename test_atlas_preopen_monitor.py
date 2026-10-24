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


def ws_quote(stamp):
    iso=stamp.isoformat()
    # KST has no daylight-saving offset.
    exchange_hhmmss=(stamp+timedelta(hours=9)).strftime("%H%M%S")
    return {"현재가":102,"quote_market":"J","market_date":"20261016",
            "체결시간":exchange_hhmmss,
            "quote_received_utc":iso,"trade_received_utc":iso,
            "book_received_utc":iso,"program_received_utc":iso}


def test_each_krx_opening_minute_needs_its_own_authenticated_receipts():
    frozen=freeze_candidates([candidate()],"KR",now=PRE)
    for offset in range(5):
        now=OPEN+timedelta(minutes=offset,seconds=30)
        received=now-timedelta(seconds=2)
        record=minute_record(frozen,{"000660":ws_quote(received)},
                             now=now,ws_connected=True)
        assert record["minute"]==offset+1
        assert record["rows"][0]["price"]==102


def test_previous_minute_trade_cannot_fill_next_minute_even_if_fresh():
    frozen=freeze_candidates([candidate()],"KR",now=PRE)
    now=OPEN+timedelta(minutes=1,seconds=3)
    old=ws_quote(OPEN+timedelta(seconds=59))
    row=minute_record(frozen,{"000660":old},now=now,ws_connected=True)["rows"][0]
    assert row["price"] is None and row["status"].startswith("WAIT")


def test_disconnected_or_missing_channel_or_rest_receipt_is_wait():
    frozen=freeze_candidates([candidate()],"KR",now=PRE)
    now=OPEN+timedelta(seconds=30)
    q=ws_quote(now-timedelta(seconds=2))
    cases=[(q,False),(quote(102,now-timedelta(seconds=2)),True),
           ({k:v for k,v in q.items() if k!="book_received_utc"},True),
           ({**q,"program_received_utc":(now-timedelta(seconds=12)).isoformat()},True),
           ({**q,"quote_market":"NX"},True),
           ({**q,"market_date":"20261015"},True),
           ({**q,"quote_received_utc":now.isoformat()},True)]
    for sample,connected in cases:
        row=minute_record(frozen,{"000660":sample},now=now,ws_connected=connected)["rows"][0]
        assert row["price"] is None and row["status"].startswith("WAIT")


def test_us_http_receipt_is_not_an_authenticated_exchange_trade():
    us_pre=datetime(2026,10,16,13,25,tzinfo=timezone.utc)
    us_open=datetime(2026,10,16,13,30,tzinfo=timezone.utc)
    frozen=freeze_candidates([candidate()],"US",now=us_pre)
    row=minute_record(frozen,{"000660":{"현재가":102,
         "quote_received_utc":(us_open+timedelta(seconds=20)).isoformat()}},
         now=us_open+timedelta(seconds=25),ws_connected=True)["rows"][0]
    assert row["price"] is None and "미국" in row["status"]


def test_fresh_ws_receipt_with_stale_exchange_execution_is_wait():
    frozen=freeze_candidates([candidate()],"KR",now=PRE)
    now=OPEN+timedelta(minutes=1,seconds=30)
    q=ws_quote(now-timedelta(seconds=2))
    # Last execution occurred over 10 seconds before the fresh WS receipt.
    q["체결시간"]="090109"
    row=minute_record(frozen,{"000660":q},now=now,ws_connected=True)["rows"][0]
    assert row["price"] is None and row["status"].startswith("WAIT")


def test_fresh_ws_receipt_with_previous_or_invalid_execution_is_wait():
    frozen=freeze_candidates([candidate()],"KR",now=PRE)
    now=OPEN+timedelta(minutes=1,seconds=4)
    valid=ws_quote(now-timedelta(seconds=1))
    for value in ("090059","090200","090160","0901","notatime",None):
        quote={**valid}
        if value is None:
            quote.pop("체결시간")
        else:
            quote["체결시간"]=value
        row=minute_record(frozen,{"000660":quote},now=now,ws_connected=True)["rows"][0]
        assert row["price"] is None and row["status"].startswith("WAIT")
