"""Public, non-authenticated delayed US index/energy futures quotes.

Yahoo Finance continuous front-month symbols are NOT an exchange-licensed real-time
feed, and can be delayed, rate-limited or unavailable. Never present as live.
"""
from datetime import datetime, timezone
from urllib.parse import quote
import requests

FUTURES = {
    "NASDAQ100 선물": "NQ=F",
    "S&P500 선물": "ES=F",
    "WTI 선물": "CL=F",
}


def fetch_future(label, *, get=requests.get, now=None):
    if label not in FUTURES:
        raise ValueError("unknown futures label")
    now = now or datetime.now(timezone.utc)
    symbol = FUTURES[label]
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol, safe="")
    result = {"지표": label, "상태": "미수신 · 공개 시세 공급자 응답 실패",
              "공급자": "Yahoo Finance (지연·비공식)", "심볼": symbol}
    try:
        response = get(url, params={"interval":"1m","range":"1d"},
                       headers={"User-Agent":"Mozilla/5.0 (ATLAS quote monitor)"},
                       timeout=6)
        response.raise_for_status()
        body = response.json()
        charts = body["chart"]["result"]
        if not charts:
            return result
        meta = charts[0]["meta"]
        px = float(meta["regularMarketPrice"])
        ts = int(meta["regularMarketTime"])
        previous = float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0)
        age = (now.timestamp() - ts)
        if not (0 < px < 1e8 and 0 <= age <= 86400):
            return {**result, "상태":"미수신 · 가격 또는 공급자 시각 오류"}
        pct = (px / previous - 1) * 100 if previous > 0 else None
        if age > 900:
            status = "과거 시세 · 15분 초과 지연"
        else:
            status = "공개 시세 · 지연 가능 · 실시간 미검증"
        return {**result, "최근값":px, "전일대비%":round(pct,2) if pct is not None else None,
                "기준일":datetime.fromtimestamp(ts,timezone.utc).isoformat(),
                "상태":status}
    except (requests.RequestException, KeyError, ValueError, TypeError, IndexError, OverflowError):
        return result


def futures_snapshot(*, get=requests.get, now=None):
    return [fetch_future(label,get=get,now=now) for label in FUTURES]
