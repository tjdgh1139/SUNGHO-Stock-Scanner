"""Read-only quality audit for KIS snapshots. Never authorizes orders."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from atlas_quote_quality import assess_quote

def audit_latest(quote_db, audit_db, *, now_utc=None):
    now=now_utc or datetime.now(timezone.utc).isoformat()
    with sqlite3.connect("file:"+str(Path(quote_db).resolve())+"?mode=ro",uri=True) as src:
        rows=src.execute("""SELECT q.symbol,q.received_at_utc,q.price,q.volume,q.turnover
          FROM market_quotes q JOIN
          (SELECT symbol,MAX(id) AS latest_id FROM market_quotes WHERE market='KRX' GROUP BY symbol) x
          ON q.id=x.latest_id ORDER BY q.symbol""").fetchall()
    records=[]
    for symbol,stamp,price,volume,turnover in rows:
        result=assess_quote({"received_at_utc":stamp,"price":price},now_utc=now)
        if not result["usable"]:
            reason=result["reason"]
        elif volume is None or turnover is None or volume<=0 or turnover<=0:
            reason="INVALID_VOLUME_OR_TURNOVER"
        else:
            reason="UNVERIFIED_EXCHANGE_TIME"
        records.append(("KRX",symbol,now,stamp,"BLOCKED",reason))
    with sqlite3.connect(audit_db) as dest:
        dest.execute("""CREATE TABLE IF NOT EXISTS quote_quality_audit (
            id INTEGER PRIMARY KEY, market TEXT NOT NULL, symbol TEXT NOT NULL,
            checked_at_utc TEXT NOT NULL, received_at_utc TEXT,
            status TEXT NOT NULL, reason TEXT NOT NULL,
            UNIQUE(market,symbol,checked_at_utc))""")
        dest.executemany("""INSERT OR IGNORE INTO quote_quality_audit
            (market,symbol,checked_at_utc,received_at_utc,status,reason)
            VALUES (?,?,?,?,?,?)""",records)
    return {"audited":len(records),"blocked":len(records),"eligible":0}
