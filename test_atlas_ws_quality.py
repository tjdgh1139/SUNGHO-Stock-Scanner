import pytest
from atlas_ws_quality import annotate_ws_quote

BASE = {
    "quote_market": "J",
    "체결시간": "093001",
    "market_date": "20261006",
    "trade_received_utc": "2026-10-06T00:30:03+00:00",
}

@pytest.mark.parametrize(
    "name,changes,connected,subscribed,expected", [
        ("NORMAL", {}, True, True, True),
        ("DISCONNECTED", {}, False, True, False),
        ("UNSUBSCRIBED", {}, True, False, False),
        ("STALE", {"trade_received_utc": "2026-10-06T00:34:00+00:00"}, True, True, False),
    ]
)
def test_ws_quality(name, changes, connected, subscribed, expected):
    result = annotate_ws_quote(
        {**BASE, **changes},
        connected=connected,
        subscribed=subscribed,
    )
    assert result["exchange_clock_valid"] is expected, name
    assert result["signal_eligible"] is False
