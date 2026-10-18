from datetime import datetime, timezone, timedelta
from atlas_nxt_opening_radar import opening_radar

NOW = datetime(2026, 10, 19, 0, 0, 5, tzinfo=timezone.utc)

def evaluate(**kw):
    args = dict(price=1250000, previous_close=1272000,
                observed_at_utc=(NOW-timedelta(seconds=2)).isoformat(),
                session_date="20261019", verified=True,
                risk_floor=1200000, now=NOW)
    args.update(kw)
    return opening_radar(**args)

def test_verified_nxt_is_observation_not_buy():
    result = evaluate()
    assert result["status"] == "NXT_OBSERVED"
    assert result["change_pct"] < 0
    assert result["signal"] == "WAIT"
    assert not result["krx_confirmation"] and not result["buyback_verified"]

def test_stale_and_future_ticks_rejected():
    assert evaluate(observed_at_utc=(NOW-timedelta(seconds=11)).isoformat())["status"] == "UNVERIFIED"
    assert evaluate(observed_at_utc=(NOW+timedelta(seconds=1)).isoformat())["status"] == "UNVERIFIED"

def test_bad_date_and_missing_auth_rejected():
    assert evaluate(session_date="20261016")["status"] == "UNVERIFIED"
    assert evaluate(verified=False)["status"] == "UNVERIFIED"

def test_floor_is_risk_threshold_not_price_prediction():
    assert evaluate(price=1190000)["floor_breached"] is True
    assert evaluate(price=1210000)["floor_breached"] is False

def test_invalid_prices_fail_closed():
    assert evaluate(price=0)["status"] == "UNVERIFIED"
    assert evaluate(previous_close=float("nan"))["status"] == "UNVERIFIED"
