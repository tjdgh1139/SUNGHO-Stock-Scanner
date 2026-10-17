"""Append-only local paper ledger; no real orders and no file rewrites.

A durable shared database is still required for multi-user Streamlit deployment.
The append-only file is suitable for controlled local/backtest jobs only.
"""
from pathlib import Path
import json,os
from atlas_paper_ledger import performance_summary


def append_event(path,event):
    if not isinstance(event,dict) or event.get("mode")!="PAPER_ONLY":
        raise ValueError("only paper events may be recorded")
    if event.get("event") not in ("SIGNAL","PAPER_FILL","PAPER_OUTCOME"):
        raise ValueError("unknown event type")
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(event,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n"
    # append-only, flush to disk before returning; caller must serialize writers.
    with p.open("a",encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())


def read_events(path):
    p=Path(path)
    if not p.exists():
        return []
    rows=[]
    with p.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def paper_report(path,horizon="5m"):
    events=read_events(path)
    return performance_summary(events,horizon=horizon)
