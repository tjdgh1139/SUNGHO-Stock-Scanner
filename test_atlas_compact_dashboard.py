from datetime import datetime,timedelta,timezone
from atlas_compact_dashboard import compact_rows,REST_SECONDS,SCREEN_SECONDS,QUICK

NOW=datetime(2026,10,16,1,0,tzinfo=timezone.utc)

def ws_row(seconds=2):
    stamp=(NOW-timedelta(seconds=seconds)).isoformat()
    return {"quote_market":"J","market_date":"20261016",
            "trade_received_utc":stamp,"book_received_utc":stamp,
            "program_received_utc":stamp,"현재가":123456,
            "등락%":2.5,"체결강도":125,"누적거래량":1000}

def test_two_second_display_and_fifteen_second_rest():
    assert SCREEN_SECONDS==2 and REST_SECONDS==15

def test_ws_takes_priority_only_when_verified():
    r=compact_rows({"000660":{"현재가":100000,"등락%":1}},
                   {"000660":ws_row()},True,NOW)
    h=next(x for x in r if x["code"]=="000660")
    assert h["price"]==123456 and h["state"]=="LIVE · KIS WS"

def test_stale_ws_falls_back_to_rest_without_live_label():
    r=compact_rows({"000660":{"현재가":100000,"등락%":1}},
                   {"000660":ws_row(25)},True,NOW)
    h=next(x for x in r if x["code"]=="000660")
    assert h["price"]==100000 and "LIVE" not in h["state"]

def test_disconnected_ws_cannot_show_live():
    r=compact_rows({},{"000660":ws_row()},False,NOW)
    assert next(x for x in r if x["code"]=="000660")["price"] is None

def test_exact_three_stocks_and_five_core_indices():
    r=compact_rows({}, {}, False, NOW)
    assert [x["code"] for x in r]==["005930","000660","009150"]
    assert len(QUICK)==5 and "미국 변동성 VIX" in QUICK
