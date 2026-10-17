from datetime import datetime,timezone,timedelta
from atlas_prebreakout import rank_prebreakout_kr,rank_prebreakout_us

NOW=datetime(2026,10,16,1,0,tzinfo=timezone.utc)

def kr(code="000660",pct=2.2,turnover=9e9):
    return {"코드":code,"종목":code,"등락%":pct,"거래대금":turnover,
            "현재가":123000,"received_utc":NOW.isoformat(),
            "source":"KIS REST 수신 · 체결시각 미검증"}

def us(code="AMD",pct=1.4,five=1.1):
    return {"코드":code,"종목":code,"등락%":pct,"최근5분%":five,
            "거래대금":5e6,"현재가":50,"스프레드%":0.2,
            "received_utc":NOW.isoformat()}

def test_kr_three_max():
    out=rank_prebreakout_kr([kr(str(i).zfill(6)) for i in range(7)],now=NOW)
    assert len(out)==3 and all(x["판정"].startswith("상승 전조") for x in out)

def test_kr_overextended_is_not_predicted():
    assert rank_prebreakout_kr([kr(pct=12)],now=NOW)==[]

def test_kr_falling_is_not_predicted():
    assert rank_prebreakout_kr([kr(pct=-2)],now=NOW)==[]

def test_kr_missing_confirmation_stays_watch():
    out=rank_prebreakout_kr([kr()],now=NOW)
    assert out and "매수 확정 아님" in out[0]["판정"]

def test_kr_live_evidence_scores_higher():
    base=kr()
    live={**base,"source":"KIS WS · confirmed","near_intraday_high":True,
          "trade_strength":130,"program_net":10000,"turnover_acceleration":1.5}
    assert rank_prebreakout_kr([live],now=NOW)[0]["예비점수"]>rank_prebreakout_kr([base],now=NOW)[0]["예비점수"]

def test_us_early_not_current_biggest_gainer():
    out=rank_prebreakout_us([us("A",1.2),us("B",18.0),us("C",2.2)],now=NOW)
    assert len(out)==2 and "B" not in [x["코드"] for x in out]

def test_us_wide_spread_rejected():
    assert rank_prebreakout_us([{**us(),"스프레드%":2}],now=NOW)==[]

def test_stale_quotes_rejected_both():
    old=(NOW-timedelta(minutes=4)).isoformat()
    assert not rank_prebreakout_kr([{**kr(),"received_utc":old}],now=NOW)
    assert not rank_prebreakout_us([{**us(),"received_utc":old}],now=NOW)

def test_missing_us_spread_is_not_zero():
    r=us();r.pop("스프레드%")
    assert rank_prebreakout_us([r],now=NOW)==[]
