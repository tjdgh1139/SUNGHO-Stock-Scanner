from datetime import datetime,timezone,timedelta
from atlas_auto_candidates import live_ws_to_kr_quote,kr_candidate

NOW=datetime(2026,10,16,1,0,tzinfo=timezone.utc)

def ws(**kwargs):
    row={"현재가":125000,"등락%":2.2,
         "장중거래대금":9000000000,"장중거래량":100000,
         "trade_received_utc":NOW.isoformat(),
         "장중고가":126000,"체결강도":130,"프로그램순매수대금":120000000}
    row.update(kwargs)
    return row

def test_live_ws_quote_maps_verified_trade_time():
    q=live_ws_to_kr_quote(ws())
    assert q["quote_received_utc"]==NOW.isoformat()
    assert q["장중등락%"]==2.2
    r=kr_candidate("000660","SK하이닉스",q,now=NOW)
    assert r is not None and r["현재가"]==125000

def test_no_trade_receipt_does_not_invent_current_time():
    q=ws()
    q.pop("trade_received_utc")
    assert live_ws_to_kr_quote(q) is None

def test_incomplete_live_trade_does_not_invent_turnover():
    q=ws()
    q.pop("장중거래대금")
    assert live_ws_to_kr_quote(q) is None

def test_stale_live_trade_rejected():
    q=live_ws_to_kr_quote(ws(trade_received_utc=(NOW-timedelta(minutes=5)).isoformat()))
    assert kr_candidate("000660","SK하이닉스",q,now=NOW) is None
