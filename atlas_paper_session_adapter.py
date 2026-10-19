"""Paper-only persistence adapter for authenticated KR tick callbacks.

No market feed is opened here. Caller injects independently verified KIS WS
ticks and candidate lists; a no-feed invocation writes no trades.
"""
from atlas_paper_live_bridge import step_ledger
from atlas_paper_sqlite import load_state,save_events

class PaperSession:
    def __init__(self,db_path,namespace):
        self.db_path=db_path
        self.namespace=namespace
        self.state=load_state(db_path,namespace)

    def ingest(self,*,a_candidates=(),b_candidates=(),ws_rows=None,
               connected=False,venue=None,now=None):
        # Work on a recovered copy: a failed SQLite commit cannot be mistaken
        # for durable in-memory progress on the next callback.
        state=load_state(self.db_path,self.namespace)
        state,emitted=step_ledger(state,a_candidates=a_candidates,
                                 b_candidates=b_candidates,ws_rows=ws_rows,
                                 connected=connected,venue=venue,now=now)
        inserted=save_events(self.db_path,self.namespace,emitted)
        self.state=load_state(self.db_path,self.namespace)
        return {"emitted":len(emitted),"persisted":inserted,
                "paper_only":True,"real_orders_allowed":False}
