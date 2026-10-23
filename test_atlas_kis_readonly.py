from datetime import datetime, timezone
import pytest
from atlas_kis_readonly import quote_request, token_request, QuoteUnavailable

NOW = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)

class Response:
    def __init__(self, data, status=200):
        self.data=data; self.status=status
    def raise_for_status(self):
        if self.status>=400:
            import requests
            raise requests.HTTPError("bad status")
    def json(self):return self.data

def get_success(url, **kwargs):
    assert kwargs["headers"]["tr_id"]=="FHKST01010100"
    assert kwargs["params"]["FID_INPUT_ISCD"]=="000660"
    return Response({"rt_cd":"0","output":{"stck_prpr":"123400","prdy_ctrt":"2.77",
                                          "acml_vol":"3226250","acml_tr_pbmn":"300000000000"}})

def test_quote_is_explicitly_not_verified_live():
    r=quote_request("000660","key","secret","token",get=get_success,now=NOW)
    assert r["현재가"]==123400 and r["누적거래량"]==3226250
    assert r["freshness"]=="REST_RECEIPT_ONLY"
    assert "프로그램순매수대금" not in r and "trade_received_utc" not in r

def test_disallowed_code_fails_closed():
    with pytest.raises(QuoteUnavailable):
        quote_request("999999","key","secret","token",get=get_success)

def test_bad_market_fails_closed():
    with pytest.raises(QuoteUnavailable):
        quote_request("000660","key","secret","token",get=get_success,market="UNKNOWN")

def test_error_payload_fails_closed():
    with pytest.raises(QuoteUnavailable):
        quote_request("000660","key","secret","token",
                      get=lambda *a,**k:Response({"rt_cd":"1","msg1":"error"}))

def test_zero_price_fails_closed():
    with pytest.raises(QuoteUnavailable):
        quote_request("000660","key","secret","token",
                      get=lambda *a,**k:Response({"rt_cd":"0","output":{
                          "stck_prpr":"0","prdy_ctrt":"0","acml_vol":"1","acml_tr_pbmn":"1"}}))

def test_token_missing_secrets():
    with pytest.raises(QuoteUnavailable):
        token_request("","")

def test_token_success():
    assert token_request("key","secret",
           post=lambda *a,**k:Response({"access_token":"token"}))=="token"

def test_monitor_page_without_secrets_fails_closed():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    page = Path(__file__).with_name("pages") / "01_ATLAS_Live_Monitor.py"
    app = AppTest.from_file(str(page), default_timeout=20).run()
    assert not app.exception
    assert any("KIS 인증정보 미설정" in x.value for x in app.error)

def test_explicit_allowlist_accepts_new_symbol_without_live_network():
    def fake_get(url, **kwargs):
        assert kwargs["params"]["FID_INPUT_ISCD"] == "012450"
        return Response({"rt_cd":"0","output":{"stck_prpr":"1000",
            "prdy_ctrt":"0","acml_vol":"10","acml_tr_pbmn":"10000"}})
    result=quote_request("012450","key","secret","token",
                         get=fake_get,now=NOW,allowed_codes=("012450",))
    assert result["freshness"]=="REST_RECEIPT_ONLY"

def test_explicit_allowlist_does_not_allow_other_codes():
    with pytest.raises(QuoteUnavailable):
        quote_request("000660","key","secret","token",
                      allowed_codes=("012450",),get=get_success)

def test_invalid_symbol_rejected_before_network():
    with pytest.raises(QuoteUnavailable):
        quote_request("00066X","key","secret","token",
                      allowed_codes=("00066X",),get=get_success)

def test_http_429_has_typed_error_without_retry():
    from atlas_kis_readonly import QuoteRateLimited
    calls=[]
    class LimitedResponse:
        status_code=429
        def raise_for_status(self):
            raise AssertionError("must detect 429 before generic raise")
    def limited_get(*args,**kwargs):
        calls.append(1)
        return LimitedResponse()
    with pytest.raises(QuoteRateLimited):
        quote_request("000660","key","secret","token",get=limited_get)
    assert len(calls)==1
