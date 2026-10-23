from datetime import timedelta
from test_flow_adapter import NOW, sample
from atlas_safe_flow import evaluate_safe_flow

def test_unverified_provider_blocks_spoofed_label():
    a, b = sample()
    for row in (a, b):
        row["freshness"] = "VERIFIED_EXCHANGE_TIME"
    result = evaluate_safe_flow(a, b, now=NOW + timedelta(minutes=1, seconds=10), expected_turnover_per_min=100_000_000)
    assert result["signal"] == "WAIT"
    assert result["quality_blocked"] is True
    assert result["reason"] == "VERIFIED_PROVIDER_NOT_CONNECTED"

def test_rest_data_remains_blocked():
    a, b = sample()
    for row in (a, b):
        row["freshness"] = "REST_RECEIPT_ONLY"
    result = evaluate_safe_flow(a, b, now=NOW + timedelta(minutes=1, seconds=10), expected_turnover_per_min=100_000_000)
    assert result["signal"] == "WAIT"
    assert result["quality_blocked"] is True
