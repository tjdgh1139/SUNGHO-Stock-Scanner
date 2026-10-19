from atlas_paper_session_adapter import PaperSession

def test_no_feed_does_not_create_paper_events(tmp_path):
    s=PaperSession(tmp_path/"paper.db","TEST")
    r=s.ingest(a_candidates=[{"symbol":"000660","score":100}],
               connected=False,venue=None)
    assert r["emitted"]==0 and r["persisted"]==0
    assert s.state["events"]==[] and not r["real_orders_allowed"]

def test_restart_recovers_empty_state(tmp_path):
    db=tmp_path/"paper.db"
    PaperSession(db,"TEST").ingest(connected=False)
    again=PaperSession(db,"TEST")
    assert again.state["signals"]=={} and again.state["fills"]=={}
