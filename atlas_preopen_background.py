"""Automated pre-open *historical* candidate snapshots, not real-time trades.

Executed by GitHub Actions at 07:00/07:55 KST. Every candidate must
have source-dated historical OHLCV, enough bars, and independent turnover
and moving-average evidence. Missing data means no recommendation.
"""
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import math

KST=ZoneInfo("Asia/Seoul")
MIN_BARS=22
MAX_EOD_AGE_DAYS=5
MIN_TURNOVER_KRW=2_000_000_000


def phase(now):
    local=now.astimezone(KST)
    if local.weekday()>4:
        return None
    minutes=local.hour*60+local.minute
    if 7*60<=minutes<7*60+50:
        return "first"
    if 7*60+50<=minutes<8*60:
        return "recheck"
    return None


def score_history(symbol,name,sector,history,*,now):
    """DataFrame with actual Date index and Close, Volume, High, Low."""
    try:
        if history is None or len(history)<MIN_BARS:
            return None
        df=history.sort_index().tail(35)
        for col in ("Close","Volume","High","Low"):
            if col not in df:
                return None
        last_date=df.index[-1]
        date=last_date.date() if hasattr(last_date,"date") else last_date
        age=(now.astimezone(KST).date()-date).days
        if not 1<=age<=MAX_EOD_AGE_DAYS:
            return None
        closes=[float(x) for x in df["Close"]]
        volumes=[float(x) for x in df["Volume"]]
        highs=[float(x) for x in df["High"]]
        lows=[float(x) for x in df["Low"]]
        if any(not math.isfinite(v) or v<=0 for v in closes+volumes+highs+lows):
            return None
        px=closes[-1]
        ma20=sum(closes[-20:])/20
        vol20=sum(volumes[-21:-1])/20
        turnover=px*volumes[-1]
        if not (turnover>=MIN_TURNOVER_KRW and vol20>0 and ma20>0):
            return None
        volume_ratio=volumes[-1]/vol20
        distance=(px/ma20-1)*100
        day=(px/closes[-2]-1)*100
        # Avoid stocks already up 10% in one day or far above MA20.
        if not (-4<=day<=6 and -5<=distance<=10 and volume_ratio>=0.8):
            return None
        high20=max(highs[-20:])
        near_high=px>=high20*0.96
        # Heuristic WATCH score, not probability of rising.
        score=round(min(95,30+min(volume_ratio,3)*10+
                  (15 if near_high else 0)+(12 if px>ma20 else 0)+
                  (8 if closes[-1]>closes[-2]>closes[-3] else 0)),1)
        return {"symbol":symbol,"name":name,"sector":sector,"score":score,
                "last_close":round(px,2),"last_trading_date":date.isoformat(),
                "volume_ratio":round(volume_ratio,2),
                "ma20_distance_pct":round(distance,2),
                "last_day_pct":round(day,2),
                "source":"FinanceDataReader historical EOD · NOT LIVE",
                "status":"WATCH · pre-open technical screen",
                "basis":"20일선·전일 거래량비·20일 고가 접근·과열 제외"}
    except (ValueError,TypeError,IndexError,KeyError,OverflowError):
        return None


def build_snapshot(universe,load_history,*,now=None,limit=5):
    now=now or datetime.now(timezone.utc)
    current_phase=phase(now)
    if current_phase is None:
        return None
    items=[]
    for code,name,sector in universe:
        try:
            history=load_history(code)
            item=score_history(code,name,sector,history,now=now)
            if item:
                items.append(item)
        except Exception:
            continue
    items.sort(key=lambda x:(x["score"],x["volume_ratio"]),reverse=True)
    return {"schema_version":1,"market":"KR",
            "session_date":now.astimezone(KST).strftime("%Y%m%d"),
            "generated_at_utc":now.isoformat(),"phase":current_phase,
            "coverage":{"attempted":len(universe),"validated":len(items)},
            "candidates":items[:limit],
            "limitations":"Historical technical screen only; news, KIS investor flows and NXT live flow not verified; no BUY signal"}
