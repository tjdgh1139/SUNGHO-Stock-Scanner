from datetime import datetime,timezone,timedelta
from atlas_candidate_signal_gate import candidate_decision

NOW=datetime(2026,10,19,1,0,tzinfo=timezone.utc)
def decide(**kw):
    d=dict(feed_verified=True,observed_at_utc=NOW.isoformat(),now=NOW,
           price=100,score=85,volume_confirmed=True,
           sector_confirmed=True,trend_confirmed=True)
    d.update(kw)
    return candidate_decision(**d)

def test_unverified_feed_waits():
    assert decide(feed_verified=False)["signal"]=="WAIT"

def test_stale_quote_waits():
    assert decide(observed_at_utc=(NOW-timedelta(seconds=11)).isoformat())["signal"]=="WAIT"

def test_missing_sector_confirmation_waits():
    assert decide(sector_confirmed=False)["signal"]=="WAIT"

def test_risk_block_waits():
    assert decide(risk_blocked=True)["signal"]=="WAIT"

def test_valid_candidate_is_nontrading_buy_signal():
    r=decide()
    assert r["signal"]=="BUY" and r["orders_enabled"] is False
