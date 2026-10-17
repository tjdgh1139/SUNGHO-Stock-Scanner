from datetime import datetime,timedelta,timezone
from atlas_nxt_revalidation import market_phase,nxt_fresh_quote,rerank_preopen_on_nxt

NXT=datetime(2026,10,16,0,0,tzinfo=timezone.utc) # 09:00 KST, not NXT
PRE=datetime(2026,10,15,23,10,tzinfo=timezone.utc) # 08:10 KST

def quote(**updates):
    row={"quote_market":"NX","market_date":"20261016",
         "trade_received_utc":(PRE-timedelta(seconds=2)).isoformat(),
         "현재가":100,"체결강도":130,"장중거래대금":100000000,
         "장중거래량":1000}
    row.update(updates)
    return row

def frozen():
    return {"market":"KR","session_date":"20261016",
            "candidates":[{"symbol":"000660","name":"SK","score":85,
                           "entry_high":105,"stop":95,"target":115},
                          {"symbol":"005930","name":"Samsung","score":80,
                           "entry_high":102,"stop":90,"target":110}]}

def test_official_nxt_window_and_krx_open():
    assert market_phase(PRE)=="NXT_PRE"
    assert market_phase(datetime(2026,10,15,23,50,tzinfo=timezone.utc))=="PREOPEN_GAP"
    assert market_phase(NXT)=="KRX_OPEN_1_5"
    assert market_phase(NXT+timedelta(minutes=5))=="KRX_REGULAR"

def test_verified_nxt_trade():
    assert nxt_fresh_quote(quote(),now=PRE)["strength"]==130

def test_krx_quote_never_passes_nxt():
    assert nxt_fresh_quote(quote(quote_market="J"),now=PRE) is None

def test_unverified_unified_venue_never_passes():
    assert nxt_fresh_quote(quote(quote_market="UN"),now=PRE) is None
    assert nxt_fresh_quote(quote(quote_market="UN",execution_venue="NX"),now=PRE)

def test_stale_or_future_trade_rejected():
    assert nxt_fresh_quote(quote(trade_received_utc=(PRE-timedelta(seconds=30)).isoformat()),now=PRE) is None
    assert nxt_fresh_quote(quote(trade_received_utc=(PRE+timedelta(seconds=10)).isoformat()),now=PRE) is None

def test_frozen_candidates_rerank_but_not_mutated():
    f=frozen()
    r=rerank_preopen_on_nxt(f,{"000660":quote(),"005930":quote(현재가=92,체결강도=105)},now=PRE)
    assert len(r)==2 and r[0]["symbol"]=="000660"
    assert "nxt_price" not in f["candidates"][0]

def test_stop_level_exclusion_and_no_invented_prices():
    r=rerank_preopen_on_nxt(frozen(),{"000660":quote(현재가=90)},now=PRE)
    assert "손절" in r[0]["status"]
    assert not rerank_preopen_on_nxt(frozen(),{"000660":quote(quote_market="J")},now=PRE)

def test_nxt_not_krx():
    assert not rerank_preopen_on_nxt(frozen(),{"000660":quote()},now=NXT)
