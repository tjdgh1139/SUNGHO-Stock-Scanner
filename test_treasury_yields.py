from datetime import date
from treasury_yields import treasury_yields

class Resp:
    text="observation_date,DGS2,DGS10,DGS30\n2026-10-14,4.20,4.80,5.10\n2026-10-15,4.30,4.90,.\n"
    def raise_for_status(self):pass

def test_fred_yields_daily_units_and_missing_values():
    rows=treasury_yields(get=lambda *a,**k:Resp(),today=date(2026,10,16))
    assert len(rows)==3
    assert rows[0]["최근값"]==4.3 and rows[1]["최근값"]==4.9
    assert rows[2]["최근값"]==5.1
    assert all("일별" in r["상태"] for r in rows)

def test_fred_stale_is_labeled():
    rows=treasury_yields(get=lambda *a,**k:Resp(),today=date(2026,10,25))
    assert all("과거" in r["상태"] for r in rows)

def test_fred_failure_fails_closed():
    class Bad:
        def raise_for_status(self):raise ValueError("fail")
    rows=treasury_yields(get=lambda *a,**k:Bad(),today=date(2026,10,16))
    assert all("최근값" not in r for r in rows)
