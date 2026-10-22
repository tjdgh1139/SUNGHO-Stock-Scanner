"""Local monotonic quote latency recorder; never stores credentials or orders."""
import sqlite3
import math
import time
from pathlib import Path

def timed_quote(symbol, provider, *, clock=None):
    clock=clock or time.monotonic
    start=clock()
    try:
        result=provider(symbol)
    except Exception:
        duration=max(0.0,clock()-start)
        return None,{"symbol":symbol,"duration_seconds":duration,"status":"FAILED"}
    duration=max(0.0,clock()-start)
    return result,{"symbol":symbol,"duration_seconds":duration,"status":"OK"}

def save_latency(db_path, event):
    if (event["status"] not in ("OK","FAILED") or
        not isinstance(event["duration_seconds"],(int,float)) or
        not math.isfinite(event["duration_seconds"]) or event["duration_seconds"]<0 or
        not isinstance(event["symbol"],str) or len(event["symbol"])!=6 or
        not event["symbol"].isascii() or not event["symbol"].isdigit()):
        raise ValueError("invalid event")
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS quote_latency (
          id INTEGER PRIMARY KEY,symbol TEXT NOT NULL,
          duration_seconds REAL NOT NULL,status TEXT NOT NULL)""")
        db.execute("INSERT INTO quote_latency(symbol,duration_seconds,status) VALUES(?,?,?)",
                   (event["symbol"],event["duration_seconds"],event["status"]))
