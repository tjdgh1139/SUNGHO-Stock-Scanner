from datetime import datetime, timezone, timedelta
from futures_quotes import fetch_future, futures_snapshot

NOW=datetime(2026,10,16,15,tzinfo=timezone.utc)

class Response:
    def __init__(self,data): self.data=data
    def raise_for_status(self): pass
    def json(self): return self.data

def sample(ts,price=20000,prev=19500):
    return Response({"chart":{"result":[{"meta":{
        "regularMarketPrice":price,"regularMarketTime":int(ts.timestamp()),
        "chartPreviousClose":prev}}]}})

def test_valid_delayed_futures_are_not_called_live():
    r=fetch_future("NASDAQ100 선물",get=lambda *a,**k:sample(NOW-timedelta(minutes=5)),now=NOW)
    assert r["최근값"]==20000 and r["전일대비%"]==2.56
    assert "실시간 미검증" in r["상태"]

def test_stale_futures_are_labeled():
    r=fetch_future("WTI 선물",get=lambda *a,**k:sample(NOW-timedelta(hours=2)),now=NOW)
    assert "15분 초과" in r["상태"]

def test_future_timestamp_never_used():
    r=fetch_future("S&P500 선물",get=lambda *a,**k:sample(NOW+timedelta(hours=1)),now=NOW)
    assert "최근값" not in r

def test_missing_provider_never_fabricates():
    r=fetch_future("WTI 선물",get=lambda *a,**k:Response({"chart":{"result":None}}),now=NOW)
    assert "최근값" not in r

def test_three_distinct_futures_symbols():
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        return sample(NOW)
    r=futures_snapshot(get=get,now=NOW)
    assert len(r)==3 and len(set(calls))==3
    assert all("최근값" in x for x in r)
