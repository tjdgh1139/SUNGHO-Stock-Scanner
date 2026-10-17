from datetime import datetime,timezone,timedelta
from foreign_flow import confirmed_flow,investor_history
from atlas_foreign_flow_panel import candidate_codes,rank_flow
import pandas as pd

NOW=datetime(2026,10,17,1,tzinfo=timezone.utc) # 10/17 10:00 KST

def rows():
    dates=("20261016","20261015","20261014","20261013","20261012")
    foreign=(4000,3000,2000,-1000,1000)
    institution=(2000,1000,1000,100,100)
    return [dict(stck_bsop_date=d,frgn_ntby_qty=str(f),
                 orgn_ntby_qty=str(i),prsn_ntby_qty=str(-f-i))
            for d,f,i in zip(dates,foreign,institution)]

def test_confirmed_accumulation():
    r=confirmed_flow("000660",rows(),now=NOW)
    assert r["foreign_3d"]==9000 and r["institution_3d"]==4000
    assert r["signal"]=="FLOW_WATCH" and r["latest_date"]=="20261016"

def test_same_day_excluded_even_if_present():
    data=rows()+[dict(stck_bsop_date="20261017",frgn_ntby_qty="9999999",
                      orgn_ntby_qty="99999",prsn_ntby_qty="-99999")]
    r=confirmed_flow("000660",data,now=NOW)
    assert r["foreign_3d"]==9000

def test_missing_institution_does_not_fabricate():
    data=rows()
    data[0].pop("orgn_ntby_qty")
    r=confirmed_flow("000660",data,now=NOW)
    assert r["foreign_1d"]==3000

def test_short_history_no_confirmed_signal():
    r=confirmed_flow("000660",rows()[:2],now=NOW)
    assert not r["confirmed"]

def test_rank_does_not_call_program_foreign():
    item=confirmed_flow("000660",rows(),now=NOW)
    item["name"]="SK하이닉스"
    r=rank_flow([item],{},False,NOW)[0]
    assert r["stage"]=="관찰/대기" and not r["live_verified"]

def test_scan_candidates_include_new_stocks():
    df=pd.DataFrame([{"코드":"012345","종목":"후보A","점수":90},
                     {"코드":"099999","종목":"후보B","점수":80}])
    result=candidate_codes(df)
    assert ("012345","후보A") in result and len(result)==5

class Response:
    def __init__(self,body):self.body=body
    def raise_for_status(self):pass
    def json(self):return self.body

def test_kis_investor_endpoint():
    def fake(url,**kwargs):
        assert url.endswith("/inquire-investor")
        assert kwargs["headers"]["tr_id"]=="FHKST01010900"
        assert kwargs["params"]["FID_INPUT_ISCD"]=="000660"
        return Response({"rt_cd":"0","output":rows()})
    assert len(investor_history("000660","k","s","token",get=fake))==5

def test_kis_error_returns_empty():
    assert investor_history("000660","k","s","token",get=lambda *a,**k:Response({"rt_cd":"1"}))==[]
