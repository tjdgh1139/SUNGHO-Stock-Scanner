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
