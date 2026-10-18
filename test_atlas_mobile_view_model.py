from atlas_mobile_view_model import compact_candidate, compact_sections

def test_unverified_never_shows_buy_or_fake_price():
    r=compact_candidate(symbol="000660",name="SK hynix",price=1230000,
        feed_verified=False,signal="BUY",observed_at_utc="2026-10-19T00:00:00Z")
    assert r["signal"]=="WAIT" and r["price"] is None
    assert r["orders_enabled"] is False

def test_verified_candidate_preserves_evidence():
    r=compact_candidate(symbol="000660",name="SK hynix",price=1230000,
        feed_verified=True,signal="BUY",observed_at_utc="2026-10-19T00:00:00Z")
    assert r["signal"]=="BUY" and r["price"]==1230000
    assert r["observed_at_utc"].endswith("+00:00")

def test_missing_timestamp_fails_closed():
    r=compact_candidate(symbol="MU",name="Micron",price=150,currency="USD",
        feed_verified=True,signal="BUY")
    assert r["signal"]=="WAIT" and r["feed_status"]=="UNVERIFIED"

def test_compact_mobile_sections():
    assert compact_sections()==("market_status","ranked_candidates","candidate_chart","paper_performance")
