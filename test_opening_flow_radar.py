from datetime import datetime,timedelta,timezone
from opening_flow_radar import opening_minute,turnover_change,rank_sector_inflows,WINDOWS

NOW=datetime(2026,10,16,0,2,tzinfo=timezone.utc)

def pair(symbol="000660",sector="semiconductor",market="KR",t=None):
    t=t or NOW
    first={"symbol":symbol,"sector":sector,"market":market,"session_date":"20261016",
           "received_utc":(t-timedelta(seconds=30)).isoformat(),
           "cumulative_turnover":1_000_000,"price":100}
    last={**first,"received_utc":t.isoformat(),
          "cumulative_turnover":4_000_000,"price":101}
    return first,last

def test_kr_open_1_3_5_minute():
    assert opening_minute(datetime(2026,10,16,0,1,tzinfo=timezone.utc),"KR")==1
    assert opening_minute(datetime(2026,10,16,0,3,tzinfo=timezone.utc),"KR")==3
    assert opening_minute(datetime(2026,10,16,0,5,tzinfo=timezone.utc),"KR")==5
    assert opening_minute(datetime(2026,10,16,0,6,tzinfo=timezone.utc),"KR") is None

def test_us_open_time():
    assert opening_minute(datetime(2026,10,16,13,31,tzinfo=timezone.utc),"US")==1

def test_turnover_delta_not_cumulative():
    a,b=pair()
    r=turnover_change(a,b,now=NOW)
    assert r["delta_turnover"]==3_000_000 and r["rate_per_min"]==6_000_000

def test_cross_stock_or_session_is_rejected():
    a,b=pair()
    b["symbol"]="005930"
    assert turnover_change(a,b,now=NOW) is None
    a,b=pair()
    b["session_date"]="20261017"
    assert turnover_change(a,b,now=NOW) is None

def test_stale_and_reset_rejected():
    a,b=pair()
    b["received_utc"]=(NOW-timedelta(minutes=5)).isoformat()
    assert turnover_change(a,b,now=NOW) is None
    a,b=pair()
    b["cumulative_turnover"]=1
    assert turnover_change(a,b,now=NOW) is None

def test_sector_coverage_required():
    rows=[pair("000660"),pair("005930")]
    expected={"semiconductor":{"000660","005930","009150"}}
    assert not rank_sector_inflows(rows,now=NOW,expected_universe=expected)

def test_sector_baseline_not_invented():
    rows=[pair("000660"),pair("005930")]
    expected={"semiconductor":{"000660","005930"}}
    r=rank_sector_inflows(rows,now=NOW,expected_universe=expected)
    assert r[0]["baseline_ratio"] is None and "unconfirmed" in r[0]["status"]

def test_sector_acceleration_and_leader():
    a,b=pair("000660")
    c,d=pair("005930")
    d["cumulative_turnover"]=8_000_000
    r=rank_sector_inflows([(a,b),(c,d)],now=NOW,
        expected_universe={"semiconductor":{"000660","005930"}},
        baseline_rates={"semiconductor":5_000_000})
    assert r[0]["baseline_ratio"]>1.5
    assert r[0]["leader"]=="005930"
    assert "confirmed" in r[0]["status"]

def test_market_currencies_never_combined():
    a,b=pair("000660",market="KR")
    c,d=pair("NVDA",market="US")
    assert not rank_sector_inflows([(a,b),(c,d)],now=NOW,
             expected_universe={"semiconductor":{"000660","NVDA"}})

def test_no_background_guarantee():
    assert WINDOWS==(1,3,5)
