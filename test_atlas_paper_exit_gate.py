from datetime import datetime,timezone,timedelta
from atlas_paper_exit_gate import paper_exit_decision
NOW=datetime(2026,10,19,2,tzinfo=timezone.utc)
def decide(**overrides):
    x=dict(entry_price=100,current_price=101,stop_price=95,target_price=110,
           feed_verified=True,observed_at_utc=NOW.isoformat(),now=NOW)
    x.update(overrides)
    return paper_exit_decision(**x)
def test_stale_never_sells():
    assert decide(observed_at_utc=(NOW-timedelta(seconds=20)).isoformat())["signal"]=="WAIT"
def test_unverified_never_sells():
    assert decide(feed_verified=False,current_price=90)["signal"]=="WAIT"
def test_stop_breach():
    assert decide(current_price=94)["reason"]=="STOP_BREACHED"
def test_target_reached():
    assert decide(current_price=111)["reason"]=="TARGET_REACHED"
def test_invalidation():
    assert decide(invalidated=True)["reason"]=="SIGNAL_INVALIDATED"
def test_no_trigger_waits():
    assert decide()["signal"]=="WAIT"
def test_no_actual_order_or_fill():
    r=decide(current_price=90)
    assert r["orders_enabled"] is False and r["paper_exit_executed"] is False
