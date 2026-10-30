"""Freeze user-selected pre-open scan and monitor minutes 1-5 after open.

All prices must come from fresh, authenticated sources. Original stop/targets
are carried forward from the scanner and never invented. No orders or claims
of trading profitability.
"""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import math

ZONE={"KR":ZoneInfo("Asia/Seoul"),"US":ZoneInfo("America/New_York")}
OPEN={"KR":(9,0),"US":(9,30)}
MAX_QUOTE_AGE=90


def _time(s):
    if not isinstance(s,str):
        return None
    try:
        d=datetime.fromisoformat(s.replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,OverflowError):
        return None


def minute_after_open(now,market):
    if market not in ZONE:
        return None
    local=now.astimezone(ZONE[market])
    if local.weekday()>=5:
        return None
    h,m=OPEN[market]
    opening=local.replace(hour=h,minute=m,second=0,microsecond=0)
    seconds=(local-opening).total_seconds()
    return int(seconds//60)+1 if 0<=seconds<300 else None


def freeze_candidates(rows,market,*,now=None,limit=5):
    now=now or datetime.now(timezone.utc)
    if market not in ZONE:
        raise ValueError("unknown market")
    local=now.astimezone(ZONE[market])
    h,m=OPEN[market]
    opening=local.replace(hour=h,minute=m,second=0,microsecond=0)
    if local.weekday()>=5 or local>=opening:
        return None
    if not isinstance(rows,list):
        return None
    frozen=[]
    for r in rows:
        if not isinstance(r,dict):
            continue
        symbol=str(r.get("코드") or "").strip()
        if not symbol or symbol in [x["symbol"] for x in frozen]:
            continue
        try:
            score=float(r.get("실시간단타점수",r.get("단타점수",r.get("점수",0))))
            if not math.isfinite(score):
                continue
        except (TypeError,ValueError):
            continue
        def price_field(*keys):
            for key in keys:
                try:
                    n=float(r[key])
                    if math.isfinite(n) and n>0:
                        return n
                except (KeyError,TypeError,ValueError):
                    pass
            return None
        frozen.append({
            "symbol":symbol,"name":str(r.get("종목") or symbol),
            "score":score,"entry_low":price_field("매수하단","매수관심하단"),
            "entry_high":price_field("매수상단","매수관심상단"),
            "stop":price_field("손절가","손절기준"),
            "target":price_field("1차목표","1차익절"),
        })
        if len(frozen)>=limit:
            break
    return {"market":market,"session_date":opening.strftime("%Y%m%d"),
            "frozen_at_utc":now.isoformat(),"candidates":frozen}


def assess_candidate(candidate,quote,*,now=None,market="KR"):
    now=now or datetime.now(timezone.utc)
    result={"status":"WAIT · 시세 미검증","price":None,"quote_age":None}
    if not isinstance(quote,dict):
        return result
    stamp=_time(quote.get("quote_received_utc"))
    if stamp is None:
        return result
    age=(now-stamp).total_seconds()
    if not 0<=age<=MAX_QUOTE_AGE:
        return {"status":"WAIT · 시세 지연","price":None,"quote_age":round(age,1)}
    try:
        px=float(quote["현재가"])
        if not math.isfinite(px) or px<=0:
            return result
    except (TypeError,ValueError,KeyError):
        return result
    if market=="KR" and quote.get("quote_market") not in ("J",):
        return result
    result={"status":"WATCH · 보유 여부 미확인","price":px,"quote_age":round(age,1)}
    stop=candidate.get("stop")
    target=candidate.get("target")
    low=candidate.get("entry_low")
    high=candidate.get("entry_high")
    if stop and px<=stop:
        result["status"]="손절 기준 이탈 · 포지션 확인"
    elif target and px>=target:
        result["status"]="1차 목표 도달 · 익절 검토"
    elif high and px>high:
        result["status"]="추격 진입 주의 · 관찰"
    elif low and px<low:
        result["status"]="진입 범위 아래 · 재검증"
    elif low and high and low<=px<=high:
        result["status"]="진입 범위 · 수급 확인 대기"
    return result



def _verified_krx_minute_receipts(quote, now):
    """Require same-minute trade and fresh independent KRX WS channel receipts.

    The caller must separately confirm its authenticated KIS WS connection.
    HTTP response receipt times cannot substitute for exchange trades.
    """
    if not isinstance(quote, dict) or quote.get("quote_market") != "J":
        return False
    if quote.get("market_date") != now.astimezone(ZONE["KR"]).strftime("%Y%m%d"):
        return False
    channel_stamps = [_time(quote.get(key)) for key in
                      ("trade_received_utc", "book_received_utc", "program_received_utc")]
    if any(stamp is None or not 0 <= (now-stamp).total_seconds() <= 10
           for stamp in channel_stamps):
        return False
    if _time(quote.get("quote_received_utc")) != channel_stamps[0]:
        return False
    now_kst = now.astimezone(ZONE["KR"])
    local_minute = now_kst.replace(second=0, microsecond=0)
    trade_minute = channel_stamps[0].astimezone(ZONE["KR"]).replace(second=0, microsecond=0)
    if trade_minute != local_minute:
        return False
    # KIS trade packet contains the EXCHANGE execution time (HHMMSS).
    # A newly received delayed/previous-minute trade is not a live observation.
    hhmmss = quote.get("체결시간")
    if not isinstance(hhmmss, str) or len(hhmmss) != 6 or not hhmmss.isascii() or not hhmmss.isdigit():
        return False
    hour, minute, second = int(hhmmss[:2]), int(hhmmss[2:4]), int(hhmmss[4:])
    if hour > 23 or minute > 59 or second > 59:
        return False
    exchange_trade = now_kst.replace(hour=hour, minute=minute, second=second, microsecond=0)
    exchange_age = (now_kst - exchange_trade).total_seconds()
    return 0 <= exchange_age <= 10 and (hour, minute) == (now_kst.hour, now_kst.minute)

def minute_record(frozen,quotes,*,now=None,ws_connected=False):
    now=now or datetime.now(timezone.utc)
    if not isinstance(frozen,dict) or frozen.get("market") not in ZONE:
        return None
    market=frozen["market"]
    local=now.astimezone(ZONE[market])
    if local.strftime("%Y%m%d")!=frozen.get("session_date"):
        return None
    minute=minute_after_open(now,market)
    if minute is None:
        return None
    rows=[]
    for candidate in frozen.get("candidates",[]):
        quote=quotes.get(candidate["symbol"])
        if market=="KR" and (not ws_connected or not _verified_krx_minute_receipts(quote,now)):
            assessment={"status":"WAIT · 해당 분 KRX 체결/호가/프로그램 미검증",
                        "price":None,"quote_age":None}
        elif market=="US":
            assessment={"status":"WAIT · 미국 거래소 체결 인증 미검증",
                        "price":None,"quote_age":None}
        else:
            assessment=assess_candidate(candidate,quote,now=now,market=market)
        rows.append({**candidate,**assessment})
    return {"minute":minute,"market":market,"observed_at_utc":now.isoformat(),
            "rows":rows}
