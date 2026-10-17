from datetime import datetime, timezone, timedelta
from atlas_collector_watchdog import collector_health

NOW = datetime(2026, 10, 19, 1, tzinfo=timezone.utc)


def stamp(seconds):
    return (NOW - timedelta(seconds=seconds)).isoformat()


def check(**overrides):
    values = dict(connected=True, heartbeat_utc=stamp(2),
                  latest_trade_utc=stamp(3), verified_symbols=2, now=NOW)
    values.update(overrides)
    return collector_health(**values)


def test_valid_authenticated_feed():
    r = check()
    assert r["status"] == "LIVE_VERIFIED"
    assert r["paper_signal_allowed"] and not r["real_orders_allowed"]


def test_connected_without_ticks_is_not_live():
    assert check(latest_trade_utc=None)["status"] == "STALE_TRADES"
    assert not check(verified_symbols=0)["paper_signal_allowed"]


def test_disconnected_and_stale_heartbeat_fail_closed():
    assert check(connected=False)["status"] == "DISCONNECTED"
    assert check(heartbeat_utc=stamp(16))["status"] == "STALE_HEARTBEAT"


def test_future_and_naive_timestamps_fail_closed():
    assert not check(latest_trade_utc=stamp(-1))["paper_signal_allowed"]
    assert not check(heartbeat_utc="2026-10-19T01:00:00")["paper_signal_allowed"]


def test_expired_trade_and_invalid_symbol_count():
    assert check(latest_trade_utc=stamp(11))["status"] == "STALE_TRADES"
    assert check(verified_symbols=True)["status"] == "NO_VERIFIED_SYMBOLS"
