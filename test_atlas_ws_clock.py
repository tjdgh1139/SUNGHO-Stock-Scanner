from ws_protocol import parse_market_packet
from atlas_exchange_clock import validate_exchange_clock

def test_ws_trade_clock():
    trade = ["0"] * 47
    trade[0] = "005930"
    trade[1] = "093001"
    trade[2] = "1000"
    trade[5] = "1.5"
    trade[18] = "120"
    trade[33] = "20261006"
    received = "2026-10-06T00:30:03+00:00"
    packet = "0|H0STCNT0|1|" + "^".join(trade)
    rows = parse_market_packet(packet, received)
    assert len(rows) == 1
    result = validate_exchange_clock(rows[0]["체결시간"], received, rows[0]["market_date"])
    assert result["valid"] is True
    assert result["lag_seconds"] == 2.0
