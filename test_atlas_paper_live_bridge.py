from datetime import datetime,timedelta,timezone
from atlas_paper_live_bridge import empty_ledger,step_ledger,session_report,validated_kr_trade

NOW=datetime(2026,10,16,0,1,tzinfo=timezone.utc) # Fri KRX 09:01

def ws(seconds=0,price=100,complete=True):
    stamp=(NOW+timedelta(seconds=seconds)).isoformat()
    row={"quote_market":"J","market_date":"20261016",
         "trade_received_utc":stamp,"book_received_utc":stamp,
         "program_received_utc":stamp,"현재가":price,
         "체결강도":130,"프로그램순매수대금":1000}
    if not complete:
        row.pop("program_received_utc")
    return row

def test_verified_kr_signal_then_distinct_fill():
    state=empty_ledger()
    a=[{"symbol":"000660","score":90,"stop":95,"target":110}]
    state,events=step_ledger(state,a_candidates=a,ws_rows={"000660":ws()},
                             connected=True,venue="J",now=NOW)
    assert len(state["signals"])==1 and not state["fills"]
    state,events=step_ledger(state,a_candidates=a,ws_rows={"000660":ws()},
                             connected=True,venue="J",now=NOW)
    assert len(state["signals"])==1 and not state["fills"]
    state,events=step_ledger(state,a_candidates=a,ws_rows={"000660":ws(2,101)},
                             connected=True,venue="J",now=NOW+timedelta(seconds=2))
    assert len(state["fills"])==1 and len(events)==1
    assert next(iter(state["fills"].values()))["paper_entry"]>101

def test_5m_outcome_uses_later_observed_tick():
    state=empty_ledger()
    a=[{"symbol":"000660","score":90,"stop":95,"target":110}]
    state,_=step_ledger(state,a_candidates=a,ws_rows={"000660":ws()},
                        connected=True,venue="J",now=NOW)
    state,_=step_ledger(state,a_candidates=a,ws_rows={"000660":ws(2,101)},
                        connected=True,venue="J",now=NOW+timedelta(seconds=2))
    state,events=step_ledger(state,a_candidates=a,ws_rows={"000660":ws(302,104)},
                        connected=True,venue="J",now=NOW+timedelta(seconds=302))
    assert len(state["outcomes"])==1
    assert events[0]["horizon"]=="5m"
    assert session_report(state)["5m"]["count"]==1

def test_disconnected_and_incomplete_ws_never_create_signal():
    a=[{"symbol":"000660"}]
    for connected,complete in [(False,True),(True,False)]:
        state,_=step_ledger(empty_ledger(),a_candidates=a,
             ws_rows={"000660":ws(complete=complete)},connected=connected,venue="J",now=NOW)
        assert not state["signals"]

def test_us_movers_not_paper_filled_from_unverified_rest():
    state,_=step_ledger(empty_ledger(),b_candidates=[{"symbol":"NVDA"}],
           ws_rows={},connected=True,venue="J",now=NOW)
    assert not state["signals"]

def test_stale_b_candidate_not_reused_next_day():
    b=[{"symbol":"000660","received_utc":(NOW-timedelta(minutes=10)).isoformat()}]
    state,_=step_ledger(empty_ledger(),b_candidates=b,ws_rows={"000660":ws()},
                        connected=True,venue="J",now=NOW)
    assert not state["signals"]

def test_fresh_b_candidate_creates_separate_signal():
    b=[{"symbol":"000660","received_utc":NOW.isoformat(),"예비점수":80}]
    state,_=step_ledger(empty_ledger(),b_candidates=b,ws_rows={"000660":ws()},
                        connected=True,venue="J",now=NOW)
    assert len(state["signals"])==1
    assert next(iter(state["signals"].values()))["origin"]=="B"

def test_no_offsession_krx_quote():
    after=datetime(2026,10,16,7,tzinfo=timezone.utc)
    r=ws()
    for key in ("trade_received_utc","book_received_utc","program_received_utc"):
        r[key]=after.isoformat()
    assert validated_kr_trade("000660",r,now=after,venue="J") is None

def test_wrong_venue_never_filled():
    state,_=step_ledger(empty_ledger(),a_candidates=[{"symbol":"000660"}],
                       ws_rows={"000660":ws()},connected=True,venue="UN",now=NOW)
    assert not state["signals"]
