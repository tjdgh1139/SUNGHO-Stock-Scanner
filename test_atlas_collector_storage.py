import json
import sqlite3
import pytest
from atlas_collector_storage import store_health_event

def event():
    return {"event":"COLLECTOR_HEALTH","observed_at_utc":"2026-10-19T00:00:00+00:00",
            "status":"DISCONNECTED","paper_signal_allowed":False,
            "real_orders_allowed":False}

def test_health_persists_after_reopen(tmp_path):
    db=tmp_path/"collector.db"
    store_health_event(db,event())
    with sqlite3.connect(db) as con:
        row=con.execute("SELECT payload FROM collector_health").fetchone()
    assert json.loads(row[0])["status"]=="DISCONNECTED"

def test_reject_order_capability(tmp_path):
    e=event()
    e["real_orders_allowed"]=True
    with pytest.raises(ValueError):
        store_health_event(tmp_path/"collector.db",e)

def test_reject_non_health_event(tmp_path):
    e=event()
    e["event"]="ORDER"
    with pytest.raises(ValueError):
        store_health_event(tmp_path/"collector.db",e)
