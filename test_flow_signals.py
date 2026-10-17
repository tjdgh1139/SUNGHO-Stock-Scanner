from datetime import datetime, timedelta, timezone
from flow_signals import evaluate_flow


T = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)


def snapshots():
    previous = dict(timestamp=T.isoformat(), price=100, cumulative_volume=1000,
                    cumulative_turnover=100_000_000, trade_strength=100,
                    program_net_krw=-10_000_000)
    current = dict(timestamp=(T + timedelta(minutes=1)).isoformat(), price=101,
                   cumulative_volume=2000, cumulative_turnover=300_000_000,
                   trade_strength=120, program_net_krw=5_000_000)
    return previous, current


def test_confirmed_candidate_with_same_clock_baseline():
    a, b = snapshots()
    r = evaluate_flow(a, b, now=T + timedelta(minutes=1, seconds=10),
                      expected_turnover_per_min=100_000_000)
    assert r["signal"] == "BUY_CANDIDATE" and r["turnover_ratio"] == 2


def test_missing_baseline_never_buys():
    a, b = snapshots()
    assert evaluate_flow(a, b, now=T + timedelta(minutes=1))["signal"] == "WAIT"


def test_stale_snapshot_never_buys():
    a, b = snapshots()
    assert evaluate_flow(a, b, now=T + timedelta(minutes=5),
                         expected_turnover_per_min=1)["signal"] == "WAIT"


def test_program_selling_blocks_candidate():
    a, b = snapshots()
    b["program_net_krw"] = -20_000_000
    assert evaluate_flow(a, b, now=T + timedelta(minutes=1),
                         expected_turnover_per_min=100_000_000)["signal"] == "WATCH"


def test_cumulative_reset_blocks_candidate():
    a, b = snapshots()
    b["cumulative_turnover"] = 100
    assert evaluate_flow(a, b, now=T + timedelta(minutes=1),
                         expected_turnover_per_min=1)["signal"] == "WAIT"


def test_future_timestamp_blocks_candidate():
    a, b = snapshots()
    assert evaluate_flow(a, b, now=T,
                         expected_turnover_per_min=1)["signal"] == "WAIT"


def test_nan_never_buys():
    a, b = snapshots()
    b["price"] = float("nan")
    assert evaluate_flow(a, b, now=T + timedelta(minutes=1),
                         expected_turnover_per_min=1)["signal"] == "WAIT"
