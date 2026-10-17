from datetime import datetime,timezone
from atlas_paper_live_bridge import live_feed_health

NOW=datetime(2026,10,16,1,tzinfo=timezone.utc)

def test_connected_without_quotes_is_not_live():
    r=live_feed_health({},True,"J",now=NOW)
    assert r["verified_symbols"]==0 and "최신 체결 없음" in r["status"]

def test_disconnected_is_not_live_even_with_rows():
    r=live_feed_health({"000660":{"현재가":100}},False,"J",now=NOW)
    assert r["verified_symbols"]==0 and r["status"]=="미연결"

def test_unsupported_venue_cannot_claim_verified():
    r=live_feed_health({"000660":{"현재가":100}},True,"UN",now=NOW)
    assert r["verified_symbols"]==0
