"""Read-only KIS REST quote adapter for ATLAS Streamlit monitoring.

Quotes are marked REST_RECEIPT_ONLY because receipt time is not exchange time.
Never interpret REST quote data as authenticated program/foreign/institution flow.
"""
from datetime import datetime, timezone
import requests

BASE_URL = "https://openapi.koreainvestment.com:9443"
WATCHLIST = (("005930", "삼성전자"), ("000660", "SK하이닉스"), ("009150", "삼성전기"))


class QuoteUnavailable(Exception):
    pass


def token_request(key, secret, *, post=requests.post):
    if not key or not secret:
        raise QuoteUnavailable("KIS API 인증정보가 설정되지 않았습니다.")
    try:
        response = post(BASE_URL + "/oauth2/tokenP",
                        json={"grant_type": "client_credentials", "appkey": key,
                              "appsecret": secret}, timeout=8)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise QuoteUnavailable("KIS 인증 토큰이 없습니다.")
        return token
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise QuoteUnavailable("KIS 인증 요청에 실패했습니다.") from exc


def quote_request(code, key, secret, token, *, get=requests.get, market="J", now=None, allowed_codes=None):
    permitted = {c for c, _ in WATCHLIST} if allowed_codes is None else set(allowed_codes)
    if not (isinstance(code,str) and len(code)==6 and code.isascii() and code.isdigit()) or code not in permitted:
        raise QuoteUnavailable("허용되지 않은 종목코드입니다.")
    if market not in ("J", "NX", "UN"):
        raise QuoteUnavailable("지원하지 않는 시장 코드입니다.")
    try:
        response = get(BASE_URL + "/uapi/domestic-stock/v1/quotations/inquire-price",
                       headers={"authorization": "Bearer " + token,
                                "appkey": key, "appsecret": secret,
                                "tr_id": "FHKST01010100", "custtype": "P"},
                       params={"FID_COND_MRKT_DIV_CODE": market,
                               "FID_INPUT_ISCD": code}, timeout=8)
        response.raise_for_status()
        body = response.json()
        if str(body.get("rt_cd")) != "0" or not isinstance(body.get("output"), dict):
            raise QuoteUnavailable("KIS 시세 응답이 정상 상태가 아닙니다.")
        data = body["output"]
        price = float(data["stck_prpr"])
        volume = float(data["acml_vol"])
        turnover = float(data["acml_tr_pbmn"])
        change = float(data["prdy_ctrt"])
        if price <= 0 or volume < 0 or turnover < 0:
            raise QuoteUnavailable("KIS 시세 값이 유효하지 않습니다.")
        stamp = now or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            raise QuoteUnavailable("시각 정보가 불완전합니다.")
        return {"코드": code, "현재가": price, "등락%": change,
                "누적거래량": volume, "누적거래대금": turnover,
                "quote_market": market, "rest_received_utc": stamp.isoformat(),
                "source": "KIS REST", "freshness": "REST_RECEIPT_ONLY"}
    except QuoteUnavailable:
        raise
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise QuoteUnavailable("KIS 현재가를 확인할 수 없습니다.") from exc
