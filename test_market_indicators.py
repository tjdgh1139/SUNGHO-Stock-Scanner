from datetime import datetime,timezone,timedelta
from market_indicators import get_indicator,INDICATORS

NOW=datetime(2026,10,16,15,tzinfo=timezone.utc)
class Resp:
    def __init__(self,body):self.body=body
    def raise_for_status(self):pass
    def json(self):return self.body

def sample(ts,px=42):
    return Resp({"chart":{"result":[{"meta":{"regularMarketPrice":px,
                    "regularMarketTime":int(ts.timestamp()),"chartPreviousClose":40}}]}})

def test_core_indicators_distinct():
    assert INDICATORS["필라델피아 반도체 SOX"][0] != INDICATORS["반도체 3배 ETF SOXL"][0]
    assert INDICATORS["미국 변동성 VIX"][0] == "^VIX"

def test_timestamp_and_source():
    r=get_indicator("미국 변동성 VIX",get=lambda *a,**k:sample(NOW-timedelta(minutes=4)),now=NOW)
    assert r["최근값"]==42 and "실시간 미검증" in r["상태"]
    assert r["기준일"].endswith("+00:00")

def test_stale_not_live():
    r=get_indicator("달러지수 DXY",get=lambda *a,**k:sample(NOW-timedelta(hours=3)),now=NOW)
    assert "15분 초과" in r["상태"]

def test_future_quote_rejected():
    r=get_indicator("미국 러셀2000",get=lambda *a,**k:sample(NOW+timedelta(hours=1)),now=NOW)
    assert "최근값" not in r

def test_missing_quote_rejected():
    r=get_indicator("브렌트유 선물",get=lambda *a,**k:Resp({"chart":{"result":[]}}),now=NOW)
    assert "최근값" not in r
