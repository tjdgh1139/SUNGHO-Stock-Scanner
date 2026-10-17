from datetime import datetime, timedelta, timezone
from flow_adapter import evaluate_kis_flow

NOW = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)

def sample():
    a = dict(코드="000660", quote_market="UN", market_date="20261016",
             trade_received_utc=NOW.isoformat(), 현재가=100,
             누적거래량=1000, 누적거래대금=100_000_000,
             체결강도=100, 프로그램순매수대금=-1_000_000)
    b = {**a, "trade_received_utc": (NOW + timedelta(minutes=1)).isoformat(),
         "현재가":101, "누적거래량":2000, "누적거래대금":300_000_000,
         "체결강도":120, "프로그램순매수대금":2_000_000}
    return a,b

def evaluate(a,b):
    return evaluate_kis_flow(a,b,now=NOW+timedelta(minutes=1,seconds=10),
                             expected_turnover_per_min=100_000_000)

def test_kis_flow_confirmed():
    a,b=sample()
    assert evaluate(a,b)["signal"]=="BUY_CANDIDATE"

def test_different_stock_never_confirms():
    a,b=sample();b["코드"]="005930"
    assert evaluate(a,b)["signal"]=="WAIT"

def test_mixed_nxt_and_krx_never_confirms():
    a,b=sample();b["quote_market"]="NX"
    assert evaluate(a,b)["signal"]=="WAIT"

def test_day_reset_never_confirms():
    a,b=sample();b["market_date"]="20261017"
    assert evaluate(a,b)["signal"]=="WAIT"

def test_missing_program_net_never_confirms():
    a,b=sample();b.pop("프로그램순매수대금")
    assert evaluate(a,b)["signal"]=="WAIT"

def test_missing_market_identity_never_confirms():
    a,b=sample();a.pop("quote_market")
    assert evaluate(a,b)["signal"]=="WAIT"
