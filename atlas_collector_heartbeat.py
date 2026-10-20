"""ATLAS collector engine operational heartbeat archive.

Records only health metadata; does not store credentials or broker tokens.
This module is not a scheduler or order executor.
"""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

SCHEMA="""
CREATE TABLE IF NOT EXISTS collector_heartbeat (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 market TEXT NOT NULL,
 observed_at_utc TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('HEALTHY','DEGRADED','HALTED')),
 reason TEXT NOT NULL,
 attempted INTEGER NOT NULL CHECK(attempted>=0),
 stored INTEGER NOT NULL CHECK(stored>=0),
 failed INTEGER NOT NULL CHECK(failed>=0)
);
CREATE INDEX IF NOT EXISTS collector_heartbeat_market_time
 ON collector_heartbeat(market,observed_at_utc DESC);
"""

def save_heartbeat(db_path: str, *, market: str, observed_at_utc: str,
                   state: str, reason: str, attempted: int,
                   stored: int, failed: int) -> None:
    stamp=datetime.fromisoformat(observed_at_utc.replace("Z","+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset()!=timezone.utc.utcoffset(stamp):
        raise ValueError("heartbeat timestamp must be UTC")
    if state not in ("HEALTHY","DEGRADED","HALTED"):
        raise ValueError("invalid health state")
    if not market or not reason or any(type(v) is not int or v<0 for v in (attempted,stored,failed)):
        raise ValueError("invalid heartbeat data")
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(SCHEMA)
        con.execute("""INSERT INTO collector_heartbeat
            (market,observed_at_utc,state,reason,attempted,stored,failed)
            VALUES (?,?,?,?,?,?,?)""",
            (market,observed_at_utc,state,reason,attempted,stored,failed))

def latest_heartbeat(db_path: str, market: str) -> dict | None:
    if not Path(db_path).exists():
        return None
    with sqlite3.connect(db_path) as con:
        con.executescript(SCHEMA)
        row=con.execute("""SELECT observed_at_utc,state,reason,attempted,stored,failed
            FROM collector_heartbeat WHERE market=?
            ORDER BY observed_at_utc DESC,id DESC LIMIT 1""",(market,)).fetchone()
    return dict(zip(("observed_at_utc","state","reason","attempted","stored","failed"),row)) if row else None
