"""Additional ATLAS macro/sector indicators from timestamped public quotes.

This feed is NOT exchange-certified real-time. Fail closed on missing or
future timestamps. Values use source-native units and explicit market labels.
"""
from datetime import datetime, timezone
from urllib.parse import quote
import requests

INDICATORS = {
    "미국 변동성 VIX": ("^VIX", "지수"),
    "달러지수 DXY": ("DX-Y.NYB", "지수"),
    "필라델피아 반도체 SOX": ("^SOX", "지수"),
    "반도체 3배 ETF SOXL": ("SOXL", "USD / 3배 ETF"),
    "미국 러셀2000": ("^RUT", "지수"),
    "달러/원 USDKRW": ("KRW=X", "KRW/USD"),
    "브렌트유 선물": ("BZ=F", "USD/배럴"),
    "금 선물": ("GC=F", "USD/트로이온스"),
    "구리 선물": ("HG=F", "USD/파운드"),
    "일본 닛케이225": ("^N225", "지수"),
    "대만 가권지수": ("^TWII", "지수"),
}


def get_indicator(name, *, get=requests.get, now=None):
    if name not in INDICATORS:
        raise ValueError("unknown indicator")
    symbol, unit = INDICATORS[name]
    result = {"지표": name, "심볼": symbol, "단위": unit,
              "상태": "미수신 · 공급자 연결 실패", "공급자": "Yahoo Finance 공개 지연시세"}
    now = now or datetime.now(timezone.utc)
    try:
        response = get("https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol,safe=""),
                       params={"interval":"1m","range":"1d"},
                       headers={"User-Agent":"Mozilla/5.0"}, timeout=6)
        response.raise_for_status()
        chart = response.json()["chart"]["result"][0]
        meta = chart["meta"]
        px = float(meta["regularMarketPrice"])
        stamp = int(meta["regularMarketTime"])
        age = now.timestamp() - stamp
        if not (0 < px < 1e8 and 0 <= age <= 172800):
            return {**result,"상태":"미수신 · 공급 시각/가격 오류"}
        prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0)
        change = round((px/prev-1)*100,2) if prev>0 else None
        status = ("과거 시세 · 15분 초과 지연" if age>900 else
                  "공개 시세 · 지연 가능 · 실시간 미검증")
        return {**result,"최근값":px,"전일대비%":change,
                "기준일":datetime.fromtimestamp(stamp,timezone.utc).isoformat(),
                "상태":status}
    except (requests.RequestException, KeyError, ValueError, TypeError, IndexError, OverflowError):
        return result


def important_indicators(*, get=requests.get, now=None):
    return [get_indicator(name,get=get,now=now) for name in INDICATORS]
