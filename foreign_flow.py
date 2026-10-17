"""KIS confirmed foreign/institutional investor flow, separate from intraday program trading.

Official KIS inquire-investor: today's row is only published after market close.
Never claim that this endpoint provides real-time foreign net buying.
"""
from datetime import datetime, timezone, time as clock_time
from zoneinfo import ZoneInfo
import math
import requests

URL="https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-investor"
KST=ZoneInfo("Asia/Seoul")


def investor_history(code,key,secret,token,*,get=requests.get):
    if not (isinstance(code,str) and len(code)==6 and code.isascii() and code.isdigit()):
        raise ValueError("invalid stock code")
    try:
        r=get(URL,headers={"authorization":"Bearer "+token,"appkey":key,
                           "appsecret":secret,"tr_id":"FHKST01010900","custtype":"P"},
              params={"FID_COND_MRKT_DIV_CODE":"J","FID_INPUT_ISCD":code},timeout=8)
        r.raise_for_status()
        payload=r.json()
        if str(payload.get("rt_cd"))!="0" or not isinstance(payload.get("output"),list):
            return []
        return payload["output"]
    except (requests.RequestException,ValueError,TypeError,KeyError):
        return []


def confirmed_flow(code,raw,*,now=None):
    now=now or datetime.now(timezone.utc)
    local=now.astimezone(KST)
    today=local.strftime("%Y%m%d")
    # KIS publishes the current day only after the market closes.
    allow_today=local.weekday()<5 and local.time()>=clock_time(16,0)
    days={}
    for row in raw:
        try:
            date=str(row["stck_bsop_date"])
            # Fail closed on current-day intraday estimates; the API is EOD-only.
            if len(date)!=8 or not date.isdigit() or date>today or (date==today and not allow_today):
                continue
            foreign=int(row["frgn_ntby_qty"])
            institution=int(row["orgn_ntby_qty"])
            personal=int(row["prsn_ntby_qty"])
            if any(abs(x)>10**11 for x in (foreign,institution,personal)):
                continue
            days[date]={"date":date,"foreign":foreign,"institution":institution,
                        "personal":personal}
        except (ValueError,KeyError,TypeError):
            continue
    if not days:
        return None
    ordered=sorted(days.values(),key=lambda x:x["date"],reverse=True)
    latest=ordered[0]
    recent=ordered[:3]
    if len(ordered)<4:
        return {"code":code,"latest_date":latest["date"],"confirmed":False,
                "reason":"confirmed history too short"}
    f3=sum(x["foreign"] for x in recent)
    i3=sum(x["institution"] for x in recent)
    fpos=sum(x["foreign"]>0 for x in recent)
    # Scores use signed shares, never a misleading division by zero/negative baseline.
    score=(25 if f3>0 else 0)+(20 if i3>0 else 0)+fpos*10
    score+=15 if latest["foreign"]>0 and latest["institution"]>0 else 0
    score+=10 if latest["foreign"]>0 and latest["foreign"]>ordered[1]["foreign"] else 0
    return {"code":code,"latest_date":latest["date"],"confirmed":True,
            "foreign_1d":latest["foreign"],"institution_1d":latest["institution"],
            "foreign_3d":f3,"institution_3d":i3,
            "foreign_buy_days":fpos,"score":min(100,score),
            "signal":"FLOW_WATCH" if f3>0 and i3>0 and fpos>=2 else "WAIT",
            "source":"KIS investor EOD · NOT LIVE"}
