"""Offline-only paper journal integration test, with explicit source gating.

No market data is invented or persisted as real. A missing authenticated feed
must never create SIGNAL, PAPER_FILL or PAPER_OUTCOME records.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from atlas_paper_live_bridge import empty_ledger, step_ledger
from atlas_paper_sqlite import save_events, load_state

def verify_no_feed_paper_safety():
    with TemporaryDirectory() as d:
        db=Path(d)/"paper.sqlite3"
        state=empty_ledger()
        state,emitted=step_ledger(state, a_candidates=[{"symbol":"000660","score":99}],
                                  connected=False, venue=None, ws_rows={})
        assert emitted==[]
        assert save_events(db,"ATLAS_STAGING",emitted)==0
        recovered=load_state(db,"ATLAS_STAGING")
        assert recovered["signals"]=={} and recovered["fills"]=={}
        assert recovered["outcomes"]=={} and recovered["events"]==[]
        return "ATLAS PAPER NO-FEED SAFETY OK"

if __name__=="__main__":
    print(verify_no_feed_paper_safety())
