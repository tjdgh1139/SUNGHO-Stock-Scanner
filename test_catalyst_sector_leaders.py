from datetime import datetime,timedelta,timezone
from catalyst_sector_leaders import verified_catalysts,sector_catalyst_ranks,rank_sector_leaders

NOW=datetime(2026,10,16,15,tzinfo=timezone.utc)

def event(**kwargs):
    return {"published_utc":NOW.isoformat(),"source_type":"official_filing",
            "event_type":"guidance","sector":"memory","source_url":"https://example.com/filing",
            "direction":"positive","verified":True,**kwargs}

def quote(**kwargs):
    return {"symbol":"TEST","sector":"memory","quote_received_utc":NOW.isoformat(),
            "price":100,"turnover":2e9,"turnover_ratio":1.8,
            "relative_strength_pct":2.0,"volume_ratio":1.6,
            "spread_pct":0.2,"flow_verified":False,**kwargs}

def test_verified_official_catalyst_ranks_sector():
    assert sector_catalyst_ranks([event()],now=NOW)[0]["sector"]=="memory"

def test_geopolitical_uncertain_not_bullish():
    e=event()
    e.update(event_type="geopolitics",direction="uncertain")
    assert sector_catalyst_ranks([e],now=NOW)==[]

def test_unverified_news_not_accepted():
    e=event();e["verified"]=False
    assert not verified_catalysts([e],now=NOW)

def test_stale_and_future_news_rejected():
    old=event();old["published_utc"]=(NOW-timedelta(days=3)).isoformat()
    future=event();future["published_utc"]=(NOW+timedelta(hours=2)).isoformat()
    assert not verified_catalysts([old,future],now=NOW)

def test_missing_url_not_evidence():
    e=event();e["source_url"]=""
    assert not verified_catalysts([e],now=NOW)

def test_duplicates_not_double_counted():
    assert sector_catalyst_ranks([event(),event()],now=NOW)[0]["catalyst_score"]==3

def test_leader_requires_fresh_market_and_relative_strength():
    assert len(rank_sector_leaders([event()],[quote()],now=NOW))==1
    q=quote();q["relative_strength_pct"]=-1
    assert not rank_sector_leaders([event()],[q],now=NOW)

def test_stale_quote_not_ranked():
    q=quote();q["quote_received_utc"]=(NOW-timedelta(minutes=4)).isoformat()
    assert not rank_sector_leaders([event()],[q],now=NOW)

def test_missing_baseline_never_fabricated():
    q=quote();q.pop("turnover_ratio")
    assert not rank_sector_leaders([event()],[q],now=NOW)

def test_flow_not_inferred_from_catalyst():
    x=rank_sector_leaders([event()],[quote()],now=NOW)[0]
    assert not x["flow_verified"] and x["status"].startswith("WATCH")
