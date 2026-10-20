"""ATLAS paper-only recommendation follow-up metrics.

Observed snapshots are not fills. Intraday snapshot MFE/MAE are estimates,
not true high/low excursions or realizable trade returns.
"""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_signals (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 market TEXT NOT NULL,
 symbol TEXT NOT NULL,
 signal_at_utc TEXT NOT NULL,
 reference_price REAL NOT NULL CHECK(reference_price > 0),
 strategy TEXT NOT NULL,
 UNIQUE(market, symbol, signal_at_utc, strategy)
);
"""

def save_signal(db_path: str, *, market: str, symbol: str, signal_at_utc: str,
                reference_price: float, strategy: str) -> bool:
    from datetime import datetime
    stamp=datetime.fromisoformat(signal_at_utc.replace("Z","+00:00"))
    if stamp.tzinfo is None or not all((market,symbol,strategy)) or reference_price<=0:
        raise ValueError("invalid signal")
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(SCHEMA)
        cur=con.execute(
            "INSERT OR IGNORE INTO research_signals(market,symbol,signal_at_utc,reference_price,strategy) VALUES(?,?,?,?,?)",
            (market,symbol,signal_at_utc,reference_price,strategy))
        return cur.rowcount==1

def snapshot_performance(db_path: str, signal_id: int) -> dict:
    with sqlite3.connect(db_path) as con:
        con.executescript(SCHEMA)
        con.row_factory=sqlite3.Row
        row=con.execute("SELECT * FROM research_signals WHERE id=?",(signal_id,)).fetchone()
        if row is None:
            raise ValueError("unknown signal")
        quotes=con.execute(
            """SELECT price FROM market_quotes WHERE market=? AND symbol=?
               AND received_at_utc>? ORDER BY received_at_utc""",
            (row["market"],row["symbol"],row["signal_at_utc"])).fetchall()
    if not quotes:
        return {"signal_id":signal_id,"status":"NO_POST_SIGNAL_DATA"}
    prices=[float(q["price"]) for q in quotes]
    base=float(row["reference_price"])
    return {"signal_id":signal_id,"status":"SNAPSHOT_ONLY",
            "observations":len(prices),
            "mfe_pct":round((max(prices)/base-1)*100,3),
            "mae_pct":round((min(prices)/base-1)*100,3),
            "last_pct":round((prices[-1]/base-1)*100,3)}
