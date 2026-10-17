from datetime import datetime,timedelta,timezone
import pytest
from atlas_paper_ledger import new_signal,paper_fill,evaluate_paper,performance_summary

NOW=datetime(2026,10,16,0,0,tzinfo=timezone.utc)

def signal():
    return new_signal(market="KR",symbol="000660",direction="LONG",
        signal_time_utc=NOW.isoformat(),signal_price=100,stop=96,
        target=110,source="KIS authenticated trade",signal_id="test-1")

def quote(price=101,delay=10,market="KR",symbol="000660"):
    return {"market":market,"symbol":symbol,"price":price,
            "observed_at_utc":(NOW+timedelta(seconds=delay)).isoformat(),
            "session_date":"20261016","source":"KIS authenticated quote"}

def bar(minutes=5,close=105,high=106,low=100):
    return {"market":"KR","symbol":"000660",
            "observed_at_utc":(NOW+timedelta(minutes=minutes)).isoformat(),
            "close":close,"high":high,"low":low,"source":"verified bar"}

def test_signal_does_not_equal_paper_fill():
    s=signal()
    f=paper_fill(s,quote())
    assert f["paper_entry"]>101 and f["paper_entry"]!=s["signal_price"]
    assert f["mode"]=="PAPER_ONLY"

def test_future_or_stale_fill_rejected():
    assert paper_fill(signal(),quote(delay=-1)) is None
    assert paper_fill(signal(),quote(delay=180)) is None

def test_other_stock_market_rejected():
    assert paper_fill(signal(),quote(symbol="005930")) is None
    assert paper_fill(signal(),quote(market="US")) is None

def test_unknown_source_rejected():
    q=quote();q.pop("source")
    assert paper_fill(signal(),q) is None

def test_stop_target_both_touched_assume_stop_first():
    s=signal();f=paper_fill(s,quote())
    b=bar(close=101,high=115,low=94)
    result=evaluate_paper(s,f,b,horizon="5m")
    assert result["exit_reason"]=="STOP_TOUCHED_CONSERVATIVE"
    assert result["net_return_pct"]<0

def test_target_and_fees_slippage():
    s=signal();f=paper_fill(s,quote())
    result=evaluate_paper(s,f,bar(close=110,high=112,low=100),horizon="5m")
    assert result["exit_reason"]=="TARGET_TOUCHED"
    assert result["net_return_pct"] < 100*(110/101-1)

def test_missing_bar_no_result():
    s=signal();f=paper_fill(s,quote())
    b=bar();b.pop("source")
    assert evaluate_paper(s,f,b,horizon="5m") is None

def test_5min_horizon_not_future_leak():
    s=signal();f=paper_fill(s,quote())
    assert evaluate_paper(s,f,bar(minutes=30),horizon="5m") is None

def test_missing_results_not_zero():
    assert performance_summary([])=={"count":0,"status":"INSUFFICIENT_DATA"}

def test_paper_summary_not_realized_profit():
    s=signal();f=paper_fill(s,quote())
    good=evaluate_paper(s,f,bar(close=105,high=106,low=100),horizon="5m")
    summary=performance_summary([good])
    assert summary["count"]==1 and summary["status"]=="PAPER_BACKTEST_NOT_REALIZED"

def test_invalid_stop_or_target_rejected():
    with pytest.raises(ValueError):
        new_signal(market="KR",symbol="000660",direction="LONG",
                   signal_time_utc=NOW.isoformat(),signal_price=100,
                   stop=105,source="KIS")

def test_negative_or_missing_fee_not_accepted():
    assert paper_fill(signal(),quote(),fee_bps=-1) is None
