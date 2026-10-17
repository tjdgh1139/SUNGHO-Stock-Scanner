"""Autonomous *on-page* KR/US early momentum shortlist.

The candidate feed does not require the manual full scan button. It samples
the KRX listing in bounded REST batches and queries KIS first-page US movers.
Neither is an exhaustive real-time market-wide feed. Do not label BUY.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

KST=ZoneInfo("Asia/Seoul")
ET=ZoneInfo("America/New_York")
KR_BATCH=6
KR_INTERVAL=30
US_INTERVAL=60
KR_UNIVERSE_LIMIT=4000
MAX_AGE_SECONDS=150


def us_regular_hours(now):
    d=now.astimezone(ET)
    return d.weekday()<5 and (9,30)<=(d.hour,d.minute)<(16,0)


def kr_regular_hours(now):
    d=now.astimezone(KST)
    return d.weekday()<5 and (9,0)<=(d.hour,d.minute)<(15,30)


def normalized_kr_universe(listing,limit=KR_UNIVERSE_LIMIT):
    if listing is None or listing.empty:
        return []
    codecol="Code" if "Code" in listing else "Symbol" if "Symbol" in listing else None
    if codecol is None or "Name" not in listing:
        return []
    frame=listing.copy()
    if "Market" in frame:
        frame=frame[frame["Market"].astype(str).str.upper().isin(("KOSPI","KOSDAQ"))]
    for key in ("Amount","Marcap","MarketCap"):
        if key in frame:
            frame=frame.sort_values(key,ascending=False,na_position="last")
            break
    out=[]
    seen=set()
    for _,r in frame.iterrows():
        code=str(r[codecol]).zfill(6)
        if len(code)!=6 or not code.isascii() or not code.isdigit() or code in seen:
            continue
        seen.add(code)
        out.append((code,str(r["Name"])))
        if len(out)>=limit:
            break
    return out


def kr_candidate(code,name,quote,now=None):
    now=now or datetime.now(timezone.utc)
    try:
        stamp=datetime.fromisoformat(str(quote["quote_received_utc"]).replace("Z","+00:00"))
        age=(now-stamp.astimezone(timezone.utc)).total_seconds()
        px=float(quote["현재가"])
        pct=float(quote["장중등락%"])
        value=float(quote["장중거래대금"])
        volume=float(quote["장중거래량"])
        if not (0<=age<=MAX_AGE_SECONDS and 0<px<1e9 and
                0<volume and value>=3_000_000_000 and 0.2<=pct<=24):
            return None
        if not all(math.isfinite(x) for x in (px,pct,value,volume)):
            return None
        # Relative intraday volume, spread and actual foreign buying are NOT
        # available in a REST quote. This is WATCH only, never an entry.
        score=min(95,round(25+min(pct,10)*3+min(value/1e10,10)*2))
        return {"시장":"KR","종목":name,"코드":code,"현재가":px,
                "등락%":round(pct,2),"거래대금":value,"점수":score,
                "상태":"상승 관찰 · 진입 검증 전","source":"KIS REST 수신 · 체결시각 미검증",
                "received_utc":stamp.isoformat(),
                "near_intraday_high":bool(quote.get("장중고가") and px>=float(quote["장중고가"])*0.995),
                "trade_strength":quote.get("체결강도"),
                "program_net":quote.get("프로그램순매수대금")}
    except (KeyError,ValueError,TypeError,OverflowError):
        return None


def us_candidates(frame,now=None):
    now=now or datetime.now(timezone.utc)
    if frame is None or frame.empty:
        return []
    out=[]
    for _,r in frame.iterrows():
        try:
            stamp=datetime.fromisoformat(str(r["조회수신UTC"]).replace("Z","+00:00"))
            age=(now-stamp.astimezone(timezone.utc)).total_seconds()
            pct=float(r["최근5분등락%"])
            turnover=float(r["거래대금USD"])
            spread=float(r["스프레드%"])
            px=float(r["현재가"])
            if not (0<=age<=MAX_AGE_SECONDS and bool(r["기초유동성통과"]) and
                    0.3<=pct<=20 and turnover>=1_000_000 and 0<=spread<=1 and px>0):
                continue
            if not all(math.isfinite(x) for x in (pct,turnover,spread,px)):
                continue
            score=min(95,round(30+min(pct,8)*5+min(turnover/1e7,8)*2-max(0,spread-.3)*10))
            out.append({"시장":"US","종목":str(r["종목"]),"코드":str(r["코드"]),
                        "현재가":px,"등락%":round(float(r.get("당일등락%",pct)),2),
                        "최근5분%":round(pct,2),"거래대금":turnover,"점수":score,
                        "스프레드%":spread,
                        "상태":"급등 관찰 · 진입 검증 전",
                        "source":"KIS 해외 순위 첫 페이지 · 지연 미검증",
                        "received_utc":stamp.isoformat()})
        except (KeyError,ValueError,TypeError,OverflowError):
            continue
    return sorted(out,key=lambda x:(x["점수"],x["최근5분%"]),reverse=True)


def fresh_ranked(rows,now=None,max_items=5):
    now=now or datetime.now(timezone.utc)
    fresh=[]
    for r in rows:
        try:
            stamp=datetime.fromisoformat(str(r["received_utc"]).replace("Z","+00:00"))
            if 0<=(now-stamp.astimezone(timezone.utc)).total_seconds()<=MAX_AGE_SECONDS:
                fresh.append(r)
        except (KeyError,TypeError,ValueError):
            continue
    return sorted(fresh,key=lambda x:(x["점수"],x["거래대금"]),reverse=True)[:max_items]
