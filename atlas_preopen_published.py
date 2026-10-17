"""Validate published background preopen snapshot and adapt for frozen tracker."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import math
import requests

URL="https://raw.githubusercontent.com/tjdgh1139/SUNGHO-Stock-Scanner/main/data/atlas_preopen_kr_latest.json"
KST=ZoneInfo("Asia/Seoul")


def validate_snapshot(snapshot,*,now=None):
    now=now or datetime.now(timezone.utc)
    if not isinstance(snapshot,dict) or snapshot.get("schema_version")!=1:
        return None
    if snapshot.get("market")!="KR" or snapshot.get("phase") not in ("first","recheck"):
        return None
    local=now.astimezone(KST)
    if snapshot.get("session_date")!=local.strftime("%Y%m%d"):
        return None
    try:
        generated=datetime.fromisoformat(snapshot["generated_at_utc"].replace("Z","+00:00"))
        if generated.tzinfo is None:
            return None
        generated=generated.astimezone(timezone.utc)
        local_generated=generated.astimezone(KST)
        age=(now-generated).total_seconds()
        if not 0<=age<=16*3600:
            return None
        if not (local_generated.hour==7 and
                (0<=local_generated.minute<50 if snapshot["phase"]=="first"
                 else 50<=local_generated.minute<=59)):
            return None
        if local_generated.strftime("%Y%m%d")!=snapshot["session_date"]:
            return None
        coverage=snapshot["coverage"]
        attempted=int(coverage["attempted"])
        validated=int(coverage["validated"])
        if not (0<validated<=attempted<=10000):
            return None
        rows=snapshot["candidates"]
        if not isinstance(rows,list) or not 1<=len(rows)<=5 or len(rows)>validated:
            return None
        frozen=[]
        seen=set()
        for r in rows:
            symbol=str(r["symbol"])
            if not (len(symbol)==6 and symbol.isascii() and symbol.isdigit()) or symbol in seen:
                return None
            seen.add(symbol)
            score=float(r["score"])
            price=float(r["last_close"])
            if not (math.isfinite(score) and 0<=score<=100 and math.isfinite(price) and price>0):
                return None
            last_date=datetime.strptime(r["last_trading_date"],"%Y-%m-%d").date()
            if not 1<=(local_generated.date()-last_date).days<=5:
                return None
            if "NOT LIVE" not in str(r.get("source","")):
                return None
            frozen.append({"symbol":symbol,"name":str(r["name"]),
                           "score":score,"entry_low":None,"entry_high":None,
                           "stop":None,"target":None,"last_close":price,
                           "last_trading_date":last_date.isoformat(),
                           "evidence":str(r.get("basis",""))})
        return {"market":"KR","session_date":snapshot["session_date"],
                "frozen_at_utc":generated.isoformat(),"candidates":frozen,
                "phase":snapshot["phase"],"coverage":coverage,
                "source":"Automated historical EOD, not live"}
    except (KeyError,ValueError,TypeError,OverflowError):
        return None


def load_published(*,get=requests.get,now=None):
    try:
        response=get(URL,timeout=5,headers={"Cache-Control":"no-cache"})
        response.raise_for_status()
        return validate_snapshot(response.json(),now=now)
    except (requests.RequestException,ValueError,TypeError):
        return None

def should_use_automatic(existing, source, automatic):
    """Keep today's manual override, but never carry it into another day."""
    if not isinstance(automatic,dict) or not automatic.get("session_date"):
        return False
    if not isinstance(existing,dict) or existing.get("session_date")!=automatic["session_date"]:
        return True
    if source=="manual":
        return False
    return str(existing.get("frozen_at_utc",""))<str(automatic.get("frozen_at_utc",""))
