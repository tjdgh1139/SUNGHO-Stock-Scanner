"""SQLite WAL journal for ATLAS paper-only events, with idempotent replay.

Requires a persistent mounted volume for cloud durability. The default
Streamlit filesystem may be ephemeral. No real orders or credentials stored.
"""
import json
from pathlib import Path
import sqlite3

ALLOWED={"SIGNAL","PAPER_FILL","PAPER_OUTCOME"}
MAX_EVENTS=20000


def event_key(event):
    if not isinstance(event,dict) or event.get("mode")!="PAPER_ONLY":
        raise ValueError("only paper evidence accepted")
    kind=event.get("event")
    ident=event.get("id")
    if kind not in ALLOWED or not isinstance(ident,str) or not ident.strip():
        raise ValueError("invalid paper event")
    if kind=="PAPER_OUTCOME":
        horizon=event.get("horizon")
        if horizon not in ("1m","3m","5m","30m","EOD"):
            raise ValueError("invalid horizon")
        return kind+":"+ident+":"+horizon
    return kind+":"+ident


def _open(path):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(p),timeout=10)
    con.execute("PRAGMA busy_timeout=10000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS paper_events (
        namespace TEXT NOT NULL,
        event_key TEXT NOT NULL,
        payload TEXT NOT NULL,
        PRIMARY KEY(namespace,event_key)
    )""")
    return con


def save_events(path,namespace,events):
    if not isinstance(namespace,str) or not namespace.strip() or len(namespace)>128:
        raise ValueError("invalid namespace")
    if not events:
        return 0
    prepared=[(namespace,event_key(e),json.dumps(e,ensure_ascii=False,
                                         sort_keys=True,allow_nan=False)) for e in events]
    with _open(path) as con:
        before=con.total_changes
        con.executemany("INSERT OR IGNORE INTO paper_events(namespace,event_key,payload) VALUES (?,?,?)",prepared)
        return con.total_changes-before


def load_state(path,namespace):
    from atlas_paper_live_bridge import empty_ledger
    state=empty_ledger()
    if not Path(path).exists():
        return state
    with _open(path) as con:
        records=con.execute(
            "SELECT payload FROM paper_events WHERE namespace=? ORDER BY rowid LIMIT ?",
            (namespace,MAX_EVENTS+1)).fetchall()
    if len(records)>MAX_EVENTS:
        raise RuntimeError("paper ledger capacity reached: archive before continuing")
    for (raw,) in records:
        e=json.loads(raw)
        kind=e.get("event")
        key=e.get("id")
        if not key or e.get("mode")!="PAPER_ONLY":
            raise ValueError("invalid stored paper event")
        if kind=="SIGNAL":
            state["signals"][key]=e
        elif kind=="PAPER_FILL":
            state["fills"][key]=e
        elif kind=="PAPER_OUTCOME":
            state["outcomes"][(key,e["horizon"])]=e
        else:
            raise ValueError("unknown stored event")
        state["events"].append(e)
    return state
