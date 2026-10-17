"""Early pre-breakout WATCH ranking, separate from today's biggest gainers.

No model has established predictive accuracy. These rules prioritize early
accumulation/acceleration while rejecting already-extended moves. Scores are
heuristics, not probabilities or orders. Never fabricate absent confirmations.
"""
from datetime import datetime, timezone
import math

MAX_AGE=90


def _age_seconds(item, now):
    try:
        stamp=datetime.fromisoformat(str(item["received_utc"]).replace("Z","+00:00"))
        if stamp.tzinfo is None:
            return None
        age=(now-stamp.astimezone(timezone.utc)).total_seconds()
        return age if 0<=age<=MAX_AGE else None
    except (ValueError,TypeError,KeyError,OverflowError):
        return None


def _number(row,key):
    try:
        n=float(row[key])
        return n if math.isfinite(n) else None
    except (KeyError,TypeError,ValueError,OverflowError):
        return None


def rank_prebreakout_kr(items, *, now=None, limit=3):
    now=now or datetime.now(timezone.utc)
    results=[]
    for item in items:
        if _age_seconds(item,now) is None:
            continue
        pct=_number(item,"등락%")
        turnover=_number(item,"거래대금")
        price=_number(item,"현재가")
        if any(x is None for x in (pct,turnover,price)):
            continue
        # Exclude already exploded or falling candidates.
        if not (0.2<=pct<=5.0 and turnover>=3_000_000_000 and price>0):
            continue
        acceleration=_number(item,"turnover_acceleration")
        near_high=item.get("near_intraday_high") is True
        live=item.get("source","").startswith("KIS WS")
        strength=_number(item,"trade_strength")
        program=_number(item,"program_net")
        # No BUY without live evidence; partial confirmations remain WATCH.
        confirmations=[
            ("거래대금",True),
            ("거래대금 증가",acceleration is not None and acceleration>=1.2),
            ("고가 접근",near_high),
            ("체결강도",live and strength is not None and strength>=110),
            ("프로그램 순매수",live and program is not None and program>0),
        ]
        count=sum(flag for _,flag in confirmations)
        score=min(90,25+count*10+min(turnover/1e10,8)*2)
        results.append({**item,"예비점수":round(score,1),"근거":", ".join(k for k,v in confirmations if v),
                        "확인수":count,"판정":"상승 전조 관찰 · 매수 확정 아님"})
    return sorted(results,key=lambda r:(r["확인수"],r["예비점수"],r["거래대금"]),reverse=True)[:limit]


def rank_prebreakout_us(items, *, now=None, limit=3):
    now=now or datetime.now(timezone.utc)
    results=[]
    for item in items:
        if _age_seconds(item,now) is None:
            continue
        day=_number(item,"등락%")
        five=_number(item,"최근5분%")
        turnover=_number(item,"거래대금")
        price=_number(item,"현재가")
        if any(x is None for x in (day,five,turnover,price)):
            continue
        # Find early acceleration, not stocks already +10%/+20%.
        if not (-0.5<=day<=4.5 and 0.3<=five<=2.5 and turnover>=1_000_000 and price>=2):
            continue
        spread=_number(item,"스프레드%")
        if spread is None or not 0<=spread<=0.8:
            continue
        score=min(90,30+min(five,2.5)*13+min(turnover/1e7,10)*2+(8 if spread<=0.3 else 0))
        results.append({**item,"예비점수":round(score,1),
                        "근거":"최근 5분 상승 초기 · 유동성/호가 통과 · 당일 과열 제외",
                        "판정":"상승 전조 관찰 · 시세 지연 미검증"})
    return sorted(results,key=lambda r:(r["예비점수"],r["거래대금"]),reverse=True)[:limit]


def turnover_momentum(previous, current, previous_rate=None):
    """Cumulative turnover snapshots from same symbol/session.

    Returns (current KRW/s rate, acceleration ratio or None). Never infers
    momentum from a single snapshot, a reset, or an invalid time interval.
    """
    try:
        a=datetime.fromisoformat(str(previous["quote_received_utc"]).replace("Z","+00:00"))
        b=datetime.fromisoformat(str(current["quote_received_utc"]).replace("Z","+00:00"))
        seconds=(b-a).total_seconds()
        if not 1<=seconds<=180:
            return None,None
        p=float(previous["장중거래대금"])
        q=float(current["장중거래대금"])
        if not all(math.isfinite(v) for v in (p,q)) or p<0 or q<p:
            return None,None
        rate=(q-p)/seconds
        if previous_rate is None or not math.isfinite(float(previous_rate)) or float(previous_rate)<=0:
            return rate,None
        return rate,rate/float(previous_rate)
    except (ValueError,KeyError,TypeError,OverflowError):
        return None,None
