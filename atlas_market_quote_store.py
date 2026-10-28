"""ATLAS market quote archive (paper/research only; never places orders).

Stores authenticated market snapshots independently from paper trade events.
The caller must supply a verified source and quote timestamp; this module
does not infer exchange execution time from HTTP receipt time.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_quotes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 market TEXT NOT NULL,
 symbol TEXT NOT NULL,
 source TEXT NOT NULL,
 received_at_utc TEXT NOT NULL,
 price REAL NOT NULL CHECK(price > 0),
 volume REAL CHECK(volume >= 0),
 turnover REAL CHECK(turnover >= 0),
 change_pct REAL,
 payload TEXT NOT NULL,
 UNIQUE(market, symbol, source, received_at_utc)
);
CREATE INDEX IF NOT EXISTS market_quotes_lookup
 ON market_quotes(market, symbol, received_at_utc DESC);
"""

def save_quote(db_path: str, *, market: str, symbol: str, source: str,
               received_at_utc: str, price: float, volume: float | None = None,
               turnover: float | None = None, change_pct: float | None = None) -> bool:
    """Append one verified quote. Return False for an exact duplicate.

    Caller must not label REST receipt time as an exchange trade timestamp.
    """
    if not market or not symbol or not source:
        raise ValueError("market, symbol, and source are required")
    try:
        stamp = datetime.fromisoformat(received_at_utc.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("received_at_utc must be a valid UTC timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
        raise ValueError("received_at_utc must include a UTC timezone")
    # SQLite sorts this TEXT column lexically. A single fixed-width UTC format
    # keeps actual instants ordered and prevents duplicate Z/+00:00 entries.
    received_at_utc = stamp.astimezone(timezone.utc).isoformat(timespec="microseconds")
    if not (0 < float(price) < float("inf")):
        raise ValueError("invalid price")
    for value in (volume, turnover):
        if value is not None and not (0 <= float(value) < float("inf")):
            raise ValueError("invalid volume or turnover")
    if change_pct is not None and not math.isfinite(float(change_pct)):
        raise ValueError("invalid change_pct")
    payload = dict(market=market, symbol=symbol, source=source,
                   received_at_utc=received_at_utc, price=float(price),
                   volume=volume, turnover=turnover, change_pct=change_pct)
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
        result = con.execute(
            """INSERT OR IGNORE INTO market_quotes
            (market,symbol,source,received_at_utc,price,volume,turnover,change_pct,payload)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (market,symbol,source,received_at_utc,float(price),volume,turnover,
             change_pct,json.dumps(payload,ensure_ascii=False,allow_nan=False)))
        return result.rowcount == 1

def latest_quote(db_path: str, market: str, symbol: str) -> dict | None:
    if not Path(db_path).exists():
        return None
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            """SELECT payload FROM market_quotes
               WHERE market=? AND symbol=?
               ORDER BY received_at_utc DESC, id DESC LIMIT 1""",
            (market,symbol)).fetchone()
    return json.loads(row[0]) if row else None
