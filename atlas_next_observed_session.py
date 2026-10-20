"""ATLAS next-observed-session paper performance.

No invented holiday calendar: identifies the next observed local market date
in stored quotes. Does NOT claim it is the next exchange trading day if
collection coverage has gaps. Observations are not executable fills.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3

MARKET_TIMEZONES={"KRX":"Asia/Seoul","NASDAQ":"America/New_York","NYSE":"America/New_York"}

def next_observed_session(db_path: str, signal_id: int) -> dict:
    with sqlite3.connect(db_path) as con:
        con.row_factory=sqlite3.Row
        signal=con.execute("SELECT market,symbol,signal_at_utc,reference_price FROM research_signals WHERE id=?",(signal_id,)).fetchone()
        if signal is None:
            raise ValueError("unknown signal")
        market=signal["market"]
        if market not in MARKET_TIMEZONES:
            raise ValueError("unsupported market")
        tz=ZoneInfo(MARKET_TIMEZONES[market])
        t0=datetime.fromisoformat(signal["signal_at_utc"].replace("Z","+00:00"))
        if t0.tzinfo is None:
            raise ValueError("signal timezone required")
        original_day=t0.astimezone(tz).date()
        rows=con.execute(
            """SELECT received_at_utc,price FROM market_quotes
               WHERE market=? AND symbol=? AND received_at_utc>?
               ORDER BY received_at_utc,id""",
            (market,signal["symbol"],signal["signal_at_utc"])).fetchall()
    by_day={}
    for row in rows:
        try:
            stamp=datetime.fromisoformat(row["received_at_utc"].replace("Z","+00:00"))
            if stamp.tzinfo is None: continue
            day=stamp.astimezone(tz).date()
            if day>original_day:
                by_day.setdefault(day,[]).append(float(row["price"]))
        except (ValueError,TypeError):
            continue
    if not by_day:
        return {"status":"NO_NEXT_OBSERVED_SESSION"}
    day=min(by_day)
    prices=by_day[day]
    base=float(signal["reference_price"])
    if base<=0:
        raise ValueError("invalid reference price")
    return {"status":"OBSERVED_SESSION_ONLY","local_session_date":day.isoformat(),
            "observations":len(prices),"first_observed_return_pct":round((prices[0]/base-1)*100,3),
            "last_observed_return_pct":round((prices[-1]/base-1)*100,3),
            "coverage_warning":"May skip trading days; not an official next-session close"}
