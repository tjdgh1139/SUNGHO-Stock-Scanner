"""ATLAS collector event persistence, independent of Streamlit.

Append-only, paper/health-only SQLite records. No credentials or broker orders.
"""
import json
import sqlite3
from pathlib import Path

ALLOWED = {"COLLECTOR_HEALTH"}
MAX_PAYLOAD_BYTES = 8192

def store_health_event(db_path, record):
    if not isinstance(record, dict) or record.get("event") not in ALLOWED:
        raise ValueError("only collector health events are allowed")
    if record.get("real_orders_allowed") is not False:
        raise ValueError("real orders must be disabled")
    payload = json.dumps(record, ensure_ascii=False, allow_nan=False, sort_keys=True)
    if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("oversized event")
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""CREATE TABLE IF NOT EXISTS collector_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observed_at_utc TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
        con.execute("INSERT INTO collector_health(observed_at_utc,payload) VALUES (?,?)",
                    (record["observed_at_utc"], payload))
