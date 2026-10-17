from datetime import datetime,timezone,timedelta
import pandas as pd
from atlas_auto_candidates import (
    kr_regular_hours,us_regular_hours,normalized_kr_universe,
    kr_candidate,us_candidates,fresh_ranked,KR_BATCH,MAX_AGE_SECONDS
)

NOW=datetime(2026,10,16,14,0,tzinfo=timezone.utc)

def kr_quote(stamp=NOW):
    return {"현재가":150000,"장중등락%":3.5,"장중거래대금":8_000_000_000,
            "장중거래량":200000,"quote_received_utc":stamp.isoformat()}

def test_kr_candidate_requires_fresh_quote():
    assert kr_candidate("000660","SK하이닉스",kr_quote(),NOW)["상태"].startswith("상승")
    assert kr_candidate("000660","SK하이닉스",kr_quote(NOW-timedelta(minutes=4)),NOW) is None

def test_kr_missing_volume_fails_closed():
    q=kr_quote();q.pop("장중거래량")
    assert kr_candidate("000660","SK하이닉스",q,NOW) is None

def test_kr_low_turnover_is_not_candidate():
    q=kr_quote();q["장중거래대금"]=100
    assert kr_candidate("000660","SK하이닉스",q,NOW) is None

def test_us_movers_spread_liquidity_and_recent_5min():
    df=pd.DataFrame([{"조회수신UTC":NOW.isoformat(),"최근5분등락%":2.5,
        "당일등락%":7,"거래대금USD":5_000_000,"스프레드%":0.4,
        "현재가":20,"기초유동성통과":True,"종목":"TEST","코드":"TST"}])
    assert us_candidates(df,NOW)[0]["상태"].startswith("급등")
    df.at[0,"스프레드%"]=4
    assert not us_candidates(df,NOW)

def test_us_stale_not_candidate():
    df=pd.DataFrame([{"조회수신UTC":(NOW-timedelta(minutes=5)).isoformat(),
        "최근5분등락%":3,"당일등락%":7,"거래대금USD":5_000_000,
        "스프레드%":0.1,"현재가":20,"기초유동성통과":True,
        "종목":"TEST","코드":"TST"}])
    assert not us_candidates(df,NOW)

def test_universe_dedup_and_sort():
    df=pd.DataFrame([{"Code":"000660","Name":"Hynix","Market":"KOSPI","Marcap":200},
                     {"Code":"005930","Name":"Samsung","Market":"KOSPI","Marcap":300},
                     {"Code":"000660","Name":"Duplicate","Market":"KOSPI","Marcap":10},
                     {"Code":"XXXXXX","Name":"Bad","Market":"KOSDAQ","Marcap":1}])
    assert normalized_kr_universe(df)==[("005930","Samsung"),("000660","Hynix")]

def test_fresh_ranked_never_keeps_old_candidates():
    row=kr_candidate("000660","SK하이닉스",kr_quote(),NOW)
    assert len(fresh_ranked([row],NOW))==1
    assert not fresh_ranked([row],NOW+timedelta(seconds=MAX_AGE_SECONDS+1))

def test_us_and_kr_hours_distinct():
    assert kr_regular_hours(datetime(2026,10,16,1,tzinfo=timezone.utc))
    assert not us_regular_hours(datetime(2026,10,16,1,tzinfo=timezone.utc))
    assert us_regular_hours(datetime(2026,10,16,15,tzinfo=timezone.utc))
    assert KR_BATCH<=8

def test_nxt_early_liquidity_floor_is_explicit_and_watch_only():
    from atlas_prebreakout import rank_prebreakout_kr
    q=kr_quote()
    q["장중거래대금"]=250_000_000
    assert kr_candidate("000660","SK하이닉스",q,NOW) is None
    item=kr_candidate("000660","SK하이닉스",q,NOW,min_turnover=200_000_000)
    assert item and item["상태"].startswith("상승 관찰")
    assert rank_prebreakout_kr([item],now=NOW)==[]
    assert len(rank_prebreakout_kr([item],now=NOW,min_turnover=200_000_000))==1
