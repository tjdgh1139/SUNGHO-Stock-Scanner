"""ATLAS NXT 08:00 premarket -> KRX 09:00 revalidation, source-safe.

Keep the original pre-open candidates immutable. Rerank only when
authenticated, fresh NXT observations exist; never silently substitute KRX
prices for NXT or treat traded turnover as net foreign buying.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

KST=ZoneInfo("Asia/Seoul")
MAX_AGE_SECONDS=15


def market_phase(now):
    k=now.astimezone(KST)
    if k.weekday()>=5:
        return "CLOSED"
    m=k.hour*60+k.minute
    if 8*60<=m<8*60+50:
        return "NXT_PRE"
    if 8*60+50<=m<9*60:
        return "PREOPEN_GAP"
    if 9*60<=m<9*60+5:
        return "KRX_OPEN_1_5"
    if 9*60+5<=m<15*60+30:
        return "KRX_REGULAR"
    return "OUT_OF_SESSION"


def nxt_fresh_quote(row,*,now=None):
    now=now or datetime.now(timezone.utc)
    if market_phase(now)!="NXT_PRE" or not isinstance(row,dict):
        return None
    try:
        market=row["quote_market"]
        if market not in ("NX","UN"):
            return None
        if market=="UN" and row.get("execution_venue")!="NX":
            return None
        if row.get("market_date")!=now.astimezone(KST).strftime("%Y%m%d"):
            return None
        stamp=datetime.fromisoformat(str(row["trade_received_utc"]).replace("Z","+00:00"))
        if stamp.tzinfo is None:
            return None
        age=(now-stamp.astimezone(timezone.utc)).total_seconds()
        price=float(row["현재가"])
        strength=float(row["체결강도"])
        turnover=float(row["장중거래대금"])
        volume=float(row["장중거래량"])
        if not (0<=age<=MAX_AGE_SECONDS and price>0 and turnover>=0 and volume>0
                and all(math.isfinite(v) for v in (price,strength,turnover,volume))):
            return None
        return {"price":price,"strength":strength,"turnover":turnover,
                "volume":volume,"age_seconds":round(age,1),
                "received_utc":stamp.astimezone(timezone.utc).isoformat()}
    except (KeyError,ValueError,TypeError,OverflowError):
        return None


def rerank_preopen_on_nxt(frozen,quotes,*,now=None,limit=5):
    now=now or datetime.now(timezone.utc)
    if not isinstance(frozen,dict) or frozen.get("market")!="KR":
        return []
    if frozen.get("session_date")!=now.astimezone(KST).strftime("%Y%m%d"):
        return []
    out=[]
    for c in frozen.get("candidates",[]):
        q=nxt_fresh_quote(quotes.get(c.get("symbol")),now=now)
        if q is None:
            continue
        stop=c.get("stop")
        high=c.get("entry_high")
        target=c.get("target")
        invalid=stop is not None and q["price"]<=stop
        chase=high is not None and q["price"]>high
        # This is relative ranking only, not an estimated rise probability.
        score=float(c.get("score") or 0)+min(q["strength"],180)/20
        if invalid:
            score-=100
        if chase:
            score-=15
        out.append({**c,"nxt_price":q["price"],"nxt_age_seconds":q["age_seconds"],
                    "nxt_strength":q["strength"],"recheck_score":round(score,2),
                    "status":"손절 기준 이탈 · 제외 검토" if invalid else
                             "추격 주의 · 대기" if chase else
                             "NXT 수급 재확인 · WATCH",
                    "source":"KIS NXT trade verified · no net investor inference"})
    return sorted(out,key=lambda x:x["recheck_score"],reverse=True)[:limit]
