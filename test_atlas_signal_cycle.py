from datetime import datetime,timezone,timedelta
from atlas_signal_cycle import signal_cycle
NOW=datetime(2026,10,19,2,tzinfo=timezone.utc)
def cycle(**kw):
    d=dict(now=NOW,observed_at_utc=NOW.isoformat(),feed_verified=True,
           price=100,score=90,volume_confirmed=True,
           sector_confirmed=True,trend_confirmed=True)
    d.update(kw)
    return signal_cycle(**d)
def test_entry_buy_advisory_only():
    r=cycle()
    assert r["signal"]=="BUY" and not r["executed"] and not r["real_orders_allowed"]
def test_entry_risk_wait():
    assert cycle(risk_blocked=True)["signal"]=="WAIT"
def test_open_position_waits_before_target():
    assert cycle(position_open=True,entry_price=100,price=102,stop_price=95,target_price=110)["signal"]=="WAIT"
def test_open_position_stop_advisory():
    r=cycle(position_open=True,entry_price=100,price=94,stop_price=95,target_price=110)
    assert r["signal"]=="SELL" and not r["executed"]
def test_open_position_target_advisory():
    assert cycle(position_open=True,entry_price=100,price=111,stop_price=95,target_price=110)["reason"]=="TARGET_REACHED"
def test_open_position_invalidation():
    assert cycle(position_open=True,entry_price=100,price=101,stop_price=95,target_price=110,invalidated=True)["reason"]=="SIGNAL_INVALIDATED"
def test_stale_feed_fails_closed_for_entry_and_exit():
    stamp=(NOW-timedelta(seconds=30)).isoformat()
    assert cycle(observed_at_utc=stamp)["signal"]=="WAIT"
    assert cycle(position_open=True,entry_price=100,price=94,stop_price=95,target_price=110,observed_at_utc=stamp)["signal"]=="WAIT"
