from datetime import datetime, timezone
from atlas_collector_market_gate import market_poll

NOW=datetime(2026,10,19,0,5,tzinfo=timezone.utc)

def test_missing_calendar_does_not_poll():
    called=[]
    def source():
        called.append(1)
        return {}
    saved=[]
    r=market_poll(source,saved.append,venue="KRX",now=NOW)
    assert r["paper_signal_allowed"] is False and not called
    assert saved[0]["real_orders_allowed"] is False

def test_verified_calendar_allows_feed_check_but_not_fake_live():
    saved=[]
    r=market_poll(lambda:{"connected":True,"verified_symbols":0},
                  saved.append,venue="KRX",now=NOW,calendar_verified=True)
    assert r["status"]!="LIVE_VERIFIED"
    assert r["real_orders_allowed"] is False

def test_holiday_blocks_feed():
    called=[]
    def source():
        called.append(1)
        return {}
    r=market_poll(source,lambda _:None,venue="KRX",now=NOW,
                  calendar_verified=True,kr_holiday=True)
    assert not called and r["paper_signal_allowed"] is False
