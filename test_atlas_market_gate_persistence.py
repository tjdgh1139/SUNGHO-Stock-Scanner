from datetime import datetime, timezone
from atlas_collector_market_gate import market_poll

NOW=datetime(2026,10,19,0,5,tzinfo=timezone.utc)

def test_saved_health_contains_venue():
    saved=[]
    result=market_poll(lambda:{"connected":False,"verified_symbols":0},
                       saved.append,venue="KRX",now=NOW,calendar_verified=True)
    assert result["venue"]=="KRX"
    assert saved[0]["venue"]=="KRX"
    assert saved[0]["paper_signal_allowed"] is False

def test_nxt_and_krx_remain_distinct():
    saved=[]
    for venue in ("NXT","KRX"):
        market_poll(lambda:{"connected":False,"verified_symbols":0},
                    saved.append,venue=venue,now=NOW,calendar_verified=True)
    assert [e["venue"] for e in saved]==["NXT","KRX"]
