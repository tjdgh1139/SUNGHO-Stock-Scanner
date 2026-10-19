"""Durable paper-session regression tests, no broker or market feed."""
from datetime import datetime,timezone
from atlas_paper_session_adapter import PaperSession
from atlas_paper_sqlite import save_events,load_state

def _signal(ident="TEST-SIGNAL"):
    return {"event":"SIGNAL","id":ident,"mode":"PAPER_ONLY",
            "market":"KR","symbol":"000660","direction":"LONG",
            "signal_time_utc":"2026-10-19T00:00:00+00:00",
            "signal_price":100.0,"source":"OFFLINE_TEST_ONLY"}

def test_nonempty_signal_survives_session_recreation(tmp_path):
    db=tmp_path/"paper.sqlite3"
    assert save_events(db,"RESTART_TEST",[_signal()])==1
    recovered=PaperSession(db,"RESTART_TEST")
    assert list(recovered.state["signals"])==["TEST-SIGNAL"]
    assert recovered.state["events"][0]["source"]=="OFFLINE_TEST_ONLY"

def test_duplicate_replay_is_idempotent(tmp_path):
    db=tmp_path/"paper.sqlite3"
    event=_signal()
    assert save_events(db,"RESTART_TEST",[event])==1
    assert save_events(db,"RESTART_TEST",[event])==0
    assert len(load_state(db,"RESTART_TEST")["events"])==1

def test_namespace_isolation_and_no_feed(tmp_path):
    db=tmp_path/"paper.sqlite3"
    save_events(db,"RESTART_TEST",[_signal()])
    staging=PaperSession(db,"STAGING_NO_FEED")
    result=staging.ingest(connected=False,venue=None)
    assert result["persisted"]==0 and result["emitted"]==0
    assert staging.state["events"]==[]
    assert len(PaperSession(db,"RESTART_TEST").state["events"])==1
