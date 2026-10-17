from datetime import datetime,timedelta,timezone
import sqlite3
import pytest
from atlas_paper_sqlite import save_events,load_state,event_key
from atlas_paper_ledger import new_signal
from atlas_paper_live_bridge import empty_ledger

NOW=datetime(2026,10,16,1,tzinfo=timezone.utc)

def signal(ident="20261016:KR:A:000660"):
    return new_signal(market="KR",symbol="000660",direction="LONG",
        signal_time_utc=NOW.isoformat(),signal_price=100,
        source="verified KIS WS",signal_id=ident)

def fill(ident="20261016:KR:A:000660"):
    return {"event":"PAPER_FILL","id":ident,"market":"KR","symbol":"000660",
            "observed_at_utc":(NOW+timedelta(seconds=5)).isoformat(),
            "observed_price":101,"paper_entry":101.1,
            "fee_bps_per_side":5,"slippage_bps_per_side":10,
            "source":"KIS WS","mode":"PAPER_ONLY"}

def outcome(ident="20261016:KR:A:000660"):
    return {"event":"PAPER_OUTCOME","id":ident,"horizon":"5m",
            "observed_at_utc":(NOW+timedelta(minutes=5)).isoformat(),
            "observed_close":103,"paper_exit":102.9,"net_return_pct":1.5,
            "exit_reason":"MARK_TO_MARKET","source":"KIS WS","mode":"PAPER_ONLY"}

def test_atomic_auto_save_and_recovery(tmp_path):
    p=tmp_path/"journal.db"
    events=[signal(),fill(),outcome()]
    assert save_events(p,"private-atlas",events)==3
    restored=load_state(p,"private-atlas")
    assert len(restored["signals"])==1
    assert len(restored["fills"])==1
    assert len(restored["outcomes"])==1
    assert len(restored["events"])==3
    assert save_events(p,"private-atlas",events)==0
    assert len(load_state(p,"private-atlas")["events"])==3

def test_separate_namespace_isolated(tmp_path):
    p=tmp_path/"journal.db"
    save_events(p,"alpha",[signal()])
    assert not load_state(p,"beta")["signals"]

def test_no_real_order_or_invalid_event_accepted(tmp_path):
    p=tmp_path/"journal.db"
    with pytest.raises(ValueError):
        save_events(p,"alpha",[{"event":"REAL_ORDER","id":"x","mode":"LIVE"}])
    assert not p.exists()

def test_batch_rollback_on_invalid_event(tmp_path):
    p=tmp_path/"journal.db"
    with pytest.raises(ValueError):
        save_events(p,"alpha",[signal(),{"event":"REAL_ORDER","id":"bad","mode":"LIVE"}])
    assert not p.exists()

def test_distinct_horizon_kept(tmp_path):
    p=tmp_path/"journal.db"
    e=outcome()
    e2={**e,"horizon":"30m"}
    assert save_events(p,"alpha",[e,e2])==2
    assert len(load_state(p,"alpha")["outcomes"])==2

def test_namespace_is_required(tmp_path):
    with pytest.raises(ValueError):
        save_events(tmp_path/"x.db","",[signal()])

def test_unconfigured_path_has_empty_state(tmp_path):
    assert load_state(tmp_path/"nonexistent.db","alpha")==empty_ledger()
