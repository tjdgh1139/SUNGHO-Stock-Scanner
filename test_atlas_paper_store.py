from atlas_paper_store import append_event,read_events,paper_report
from atlas_paper_ledger import new_signal
from datetime import datetime,timezone
import pytest

def test_append_only_paper_ledger(tmp_path):
    p=tmp_path/"journal.jsonl"
    s=new_signal(market="KR",symbol="000660",direction="LONG",
        signal_time_utc=datetime(2026,10,16,tzinfo=timezone.utc).isoformat(),
        signal_price=100,source="verified",signal_id="abc")
    append_event(p,s)
    append_event(p,{**s,"id":"def"})
    rows=read_events(p)
    assert len(rows)==2 and rows[0]["id"]=="abc" and rows[1]["id"]=="def"
    assert paper_report(p)["status"]=="INSUFFICIENT_DATA"

def test_reject_actual_trade_events(tmp_path):
    with pytest.raises(ValueError):
        append_event(tmp_path/"x",{"event":"REAL_ORDER","mode":"LIVE"})
