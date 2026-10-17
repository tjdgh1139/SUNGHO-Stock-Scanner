from datetime import datetime,timezone,timedelta
import pandas as pd
from atlas_preopen_background import phase,score_history,build_snapshot
from atlas_preopen_published import validate_snapshot,load_published

FIRST=datetime(2026,10,18,22,0,tzinfo=timezone.utc) # Sun 15:00 PDT / Mon 07:00 KST
SECOND=datetime(2026,10,18,22,55,tzinfo=timezone.utc)
OPEN=datetime(2026,10,18,23,0,tzinfo=timezone.utc)

def history(last="2026-10-16"):
    dates=pd.bdate_range(end=last,periods=30)
    return pd.DataFrame({"Close":[100000]*30,"High":[101000]*30,
                         "Low":[99000]*30,"Volume":[100000]*30},index=dates)

def test_pt_to_kst_schedule_and_phase():
    assert phase(FIRST)=="first"
    assert phase(SECOND)=="recheck"
    assert phase(OPEN) is None
    assert FIRST.astimezone(__import__("zoneinfo").ZoneInfo("America/Los_Angeles")).hour==15

def test_historical_eod_screen():
    r=score_history("000660","SK","semiconductor",history(),now=FIRST)
    assert r["last_trading_date"]=="2026-10-16"
    assert r["score"]>0 and "NOT LIVE" in r["source"]

def test_no_future_or_same_day_eod():
    assert score_history("000660","SK","semi",history("2026-10-19"),now=FIRST) is None

def test_snapshot_top5_only():
    universe=[(str(i).zfill(6),str(i),"semi") for i in range(8)]
    r=build_snapshot(universe,lambda _:history(),now=FIRST)
    assert len(r["candidates"])==5 and r["coverage"]["validated"]==8
    assert r["phase"]=="first"

def test_published_snapshot_validates_and_loads():
    r=build_snapshot([("000660","SK","semi")],lambda _:history(),now=FIRST)
    assert validate_snapshot(r,now=FIRST+timedelta(minutes=1))["candidates"][0]["symbol"]=="000660"
    class Response:
        def raise_for_status(self):pass
        def json(self):return r
    assert load_published(get=lambda *a,**k:Response(),now=FIRST)["phase"]=="first"

def test_published_snapshot_rejects_old_session_and_fake_live():
    r=build_snapshot([("000660","SK","semi")],lambda _:history(),now=FIRST)
    assert validate_snapshot(r,now=FIRST+timedelta(days=1)) is None
    r["candidates"][0]["source"]="LIVE"
    assert validate_snapshot(r,now=FIRST) is None

def test_published_snapshot_rejects_wrong_phase_time():
    r=build_snapshot([("000660","SK","semi")],lambda _:history(),now=FIRST)
    r["phase"]="recheck"
    assert validate_snapshot(r,now=FIRST) is None

def test_no_data_no_candidates():
    r=build_snapshot([("000660","SK","semi")],lambda _:None,now=FIRST)
    assert r["candidates"]==[]
    assert validate_snapshot(r,now=FIRST) is None

from atlas_market_calendar import krx_session

def test_krx_calendar_skips_weekends_and_holidays():
    assert krx_session(datetime(2026,10,19).date())
    assert not krx_session(datetime(2026,10,18).date())
    assert not krx_session(datetime(2026,10,9).date())

def test_calendar_unavailable_is_not_assumed_open():
    class Bad:
        def is_session(self,d):raise ValueError("unavailable")
    assert not krx_session(datetime(2026,10,19).date(),calendar=Bad())
