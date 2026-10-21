from datetime import timedelta
from test_flow_adapter import NOW, sample
from atlas_safe_flow import evaluate_safe_flow

def test_simulated_verified_candidate():
    a, b = sample()
    a["freshness"] = "VERIFIED_EXCHANGE_TIME"
    b["freshness"] = "VERIFIED_EXCHANGE_TIME"
    result = evaluate_safe_flow(
        a, b, now=NOW + timedelta(minutes=1, seconds=10),
        expected_turnover_per_min=100_000_000
    )
    assert result["signal"] == "BUY_CANDIDATE"

def test_rest_only_must_wait():
    a, b = sample()
    a["freshness"] = "REST_RECEIPT_ONLY"
    b["freshness"] = "REST_RECEIPT_ONLY"
    result = evaluate_safe_flow(
        a, b, now=NOW + timedelta(minutes=1, seconds=10),
        expected_turnover_per_min=100_000_000
    )
    assert result["signal"] == "WAIT"
    assert result["quality_blocked"] is True

def test_missing_freshness_must_wait():
    a, b = sample()
    result = evaluate_safe_flow(
        a, b, now=NOW + timedelta(minutes=1, seconds=10),
        expected_turnover_per_min=100_000_000
    )
    assert result["signal"] == "WAIT"
    assert result["quality_blocked"] is True
