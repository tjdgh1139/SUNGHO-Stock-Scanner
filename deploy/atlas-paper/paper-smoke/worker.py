"""Isolated no-feed paper store heartbeat; never creates synthetic trades."""
import os
import time
from atlas_paper_session_adapter import PaperSession

db=os.environ.get("ATLAS_PAPER_DB","/var/lib/atlas/paper.sqlite3")
namespace=os.environ.get("ATLAS_PAPER_NAMESPACE","STAGING_NO_FEED")
interval=max(30,int(os.environ.get("ATLAS_PAPER_INTERVAL","60")))

if __name__=="__main__":
    while True:
        session=PaperSession(db,namespace)
        result=session.ingest(connected=False,venue=None,ws_rows={})
        assert result["emitted"]==0 and result["persisted"]==0
        print("PAPER_STAGING_NO_FEED_OK",flush=True)
        time.sleep(interval)
