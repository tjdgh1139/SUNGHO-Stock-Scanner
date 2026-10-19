"""Staging-only heartbeat. No broker connection and no invented live quotes."""
import os
import time
from datetime import datetime,timezone
from atlas_collector_storage import store_health_event

DB=os.environ.get("ATLAS_HEALTH_DB","/var/lib/atlas/health.sqlite3")
INTERVAL=max(10,int(os.environ.get("ATLAS_HEALTH_INTERVAL_SECONDS","60")))

if __name__=="__main__":
    while True:
        now=datetime.now(timezone.utc)
        store_health_event(DB,{"event":"COLLECTOR_HEALTH",
            "observed_at_utc":now.isoformat(),
            "status":"STAGING_NO_FEED",
            "paper_signal_allowed":False,
            "real_orders_allowed":False})
        time.sleep(INTERVAL)
