"""Paper research follow-up checkpoints from stored quote snapshots.

Checkpoint observations are strictly at/after the target time and within a
specified tolerance. Missing coverage is MISSING, never zero return.
"""
from datetime import datetime, timedelta, timezone
import sqlite3

CHECKPOINTS_MINUTES=(5,15,30,60,1440)

def checkpoint_returns(db_path: str, signal_id: int, *, tolerance_minutes: int = 5) -> dict:
    if tolerance_minutes < 0:
        raise ValueError("negative tolerance")
    with sqlite3.connect(db_path) as con:
        con.row_factory=sqlite3.Row
        signal=con.execute(
            "SELECT market,symbol,signal_at_utc,reference_price FROM research_signals WHERE id=?",
            (signal_id,)).fetchone()
        if signal is None:
            raise ValueError("unknown signal")
        base=float(signal["reference_price"])
        if base <= 0:
            raise ValueError("invalid reference price")
        t0=datetime.fromisoformat(signal["signal_at_utc"].replace("Z","+00:00"))
        if t0.tzinfo is None:
            raise ValueError("missing timezone")
        rows=con.execute(
            """SELECT received_at_utc,price FROM market_quotes
               WHERE market=? AND symbol=? AND received_at_utc>?
               ORDER BY received_at_utc""",
            (signal["market"],signal["symbol"],signal["signal_at_utc"])).fetchall()
    observations=[]
    for row in rows:
        ts=datetime.fromisoformat(row["received_at_utc"].replace("Z","+00:00"))
        if ts.tzinfo is None: continue
        observations.append((ts.astimezone(timezone.utc),float(row["price"])))
    result={}
    for minutes in CHECKPOINTS_MINUTES:
        target=t0.astimezone(timezone.utc)+timedelta(minutes=minutes)
        end=target+timedelta(minutes=tolerance_minutes)
        match=next(((t,p) for t,p in observations if target<=t<=end),None)
        key=f"{minutes}m"
        result[key]=(
            {"status":"OBSERVED","return_pct":round((match[1]/base-1)*100,3),
             "observed_at_utc":match[0].isoformat()}
            if match else {"status":"MISSING"}
        )
    return result
