"""ATLAS first 1/3/5 minutes: validated sector money-flow radar.

Works on snapshots from a *declared coverage universe*. It never calls
cumulative turnover 'new money' or infers investor identity. Requires
two comparable snapshots from the same symbol, market and trading day.
An opening window needs observed coverage; missing snapshots are not zero.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math

KST=ZoneInfo("Asia/Seoul")
ET=ZoneInfo("America/New_York")
WINDOWS=(1,3,5)
MAX_AGE=12


def parse_utc(value):
    if not isinstance(value,str):
        return None
    try:
        x=datetime.fromisoformat(value.replace("Z","+00:00"))
        return x.astimezone(timezone.utc) if x.tzinfo else None
    except (ValueError,OverflowError):
        return None


def opening_minute(now,market):
    if market not in ("KR","US"):
        raise ValueError("unknown market")
    local=now.astimezone(KST if market=="KR" else ET)
    if local.weekday()>4:
        return None
    hour,minute=(9,0) if market=="KR" else (9,30)
    opening=local.replace(hour=hour,minute=minute,second=0,microsecond=0)
    elapsed=(local-opening).total_seconds()/60
    return elapsed if 0<=elapsed<=5 else None


def turnover_change(before,after,*,now=None):
    now=now or datetime.now(timezone.utc)
    try:
        if not all(before.get(k)==after.get(k) and before.get(k) for k in ("symbol","market","session_date")):
            return None
        t0=parse_utc(before.get("received_utc"))
        t1=parse_utc(after.get("received_utc"))
        if t0 is None or t1 is None:
            return None
        span=(t1-t0).total_seconds()
        age=(now-t1).total_seconds()
        a=float(before["cumulative_turnover"])
        b=float(after["cumulative_turnover"])
        p0=float(before["price"])
        p1=float(after["price"])
        if not (2<=span<=120 and 0<=age<=MAX_AGE and 0<=a<=b and p0>0 and p1>0):
            return None
        if not all(math.isfinite(v) for v in (a,b,p0,p1)):
            return None
        return {"symbol":after["symbol"],"market":after["market"],
                "sector":after["sector"] if before.get("sector")==after.get("sector") else None,
                "delta_turnover":b-a,"rate_per_min":(b-a)*60/span,
                "price_change_pct":(p1/p0-1)*100,"span_seconds":span,
                "received_utc":t1.isoformat()}
    except (KeyError,TypeError,ValueError,OverflowError):
        return None


def rank_sector_inflows(pairs,*,now=None,expected_universe=None,baseline_rates=None,min_coverage=0.8):
    """Rank *observed* sector activity, not verified whole-market net capital flow.

    expected_universe: {sector: set(symbols)}; requires >=80% coverage.
    baseline_rates: optional {sector: historical same-clock-time KRW/min or USD/min}.
    Missing baselines never count as zero or as an acceleration signal.
    """
    now=now or datetime.now(timezone.utc)
    expected_universe=expected_universe or {}
    baseline_rates=baseline_rates or {}
    groups={}
    for before,after in pairs:
        d=turnover_change(before,after,now=now)
        if d is None or not d["sector"] or d["delta_turnover"]<=0:
            continue
        sector=d["sector"]
        group=groups.setdefault(sector,{"sector":sector,"observed":{},"market":d["market"]})
        if group["market"]!=d["market"]:
            continue
        group["observed"][d["symbol"]]=d
    out=[]
    for sector,g in groups.items():
        universe=expected_universe.get(sector)
        if not universe:
            continue
        observed={s:v for s,v in g["observed"].items() if s in universe}
        coverage=len(observed)/len(universe) if universe else 0
        if coverage<min_coverage:
            continue
        rate=sum(x["rate_per_min"] for x in observed.values())
        baseline=baseline_rates.get(sector)
        try:
            base=float(baseline)
            ratio=rate/base if math.isfinite(base) and base>0 else None
        except (ValueError,TypeError):
            ratio=None
        rising=sum(x["price_change_pct"]>0 for x in observed.values())
        breadth=rising/len(observed)
        leaders=sorted(observed.values(),key=lambda x:x["rate_per_min"],reverse=True)
        out.append({"sector":sector,"market":g["market"],"rate_per_min":rate,
                    "baseline_ratio":ratio,"coverage":round(coverage,3),
                    "breadth":round(breadth,3),
                    "leader":leaders[0]["symbol"],"observed_count":len(observed),
                    "status":"WATCH · relative acceleration confirmed" if ratio is not None and ratio>=1.5 and breadth>=0.6
                             else "WATCH · baseline/strength unconfirmed"})
    return sorted(out,key=lambda x:(x["baseline_ratio"] is not None,
                      x["baseline_ratio"] or 0,x["rate_per_min"]),reverse=True)
