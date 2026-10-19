from datetime import datetime, timezone
import pytest
from atlas_collector_runner import poll_once, run_forever

NOW=datetime(2026,10,19,0,0,tzinfo=timezone.utc)

def test_missing_feed_is_not_live():
    saved=[]
    r=poll_once(lambda:{"connected":True,"verified_symbols":0},
                saved.append,now=NOW)
    assert r["status"]!="LIVE_VERIFIED"
    assert not r["paper_signal_allowed"] and not r["real_orders_allowed"]
    assert len(saved)==1

def test_invalid_source_fails():
    with pytest.raises(ValueError):
        poll_once(lambda:None,lambda _:None,now=NOW)

def test_sink_failure_is_not_swallowed():
    def fail(_):
        raise OSError("disk unavailable")
    with pytest.raises(OSError):
        poll_once(lambda:{"connected":False},fail,now=NOW)

def test_bad_interval_rejected():
    with pytest.raises(ValueError):
        run_forever(lambda:{},lambda _:None,interval_seconds=0,stop=lambda:True)
