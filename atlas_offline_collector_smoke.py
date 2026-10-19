"""ATLAS offline collector integration smoke test.

No broker credentials, network requests or orders. Verify market gate and
persistent storage in a temporary SQLite database before live deployment.
"""
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
import sqlite3
from atlas_collector_market_gate import market_poll
from atlas_collector_storage import store_health_event

def smoke():
    now=datetime(2026,10,19,0,5,tzinfo=timezone.utc)
    with TemporaryDirectory() as d:
        path=Path(d)/"health.sqlite3"
        def sink(record):
            store_health_event(path,record)
        observed=market_poll(lambda:{"connected":False,"verified_symbols":0},
                             sink,venue="KRX",now=now,calendar_verified=True)
        with sqlite3.connect(path) as db:
            row=db.execute("SELECT payload FROM collector_health ORDER BY id DESC LIMIT 1").fetchone()
        assert row and '"venue": "KRX"' in row[0]
        assert observed["paper_signal_allowed"] is False
        assert observed["real_orders_allowed"] is False
    return "ATLAS OFFLINE COLLECTOR SMOKE OK"

if __name__=="__main__":
    print(smoke())
