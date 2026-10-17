"""Evidence-first catalyst -> sector -> leader candidate ranking.

Pure decision-support logic: requires externally verified sources and fresh
market data; NEVER fetches headlines or claims predictive probability.
Macro/geopolitical headlines alone are not a BUY signal. Missing inputs fail
closed. A candidate can only be WATCH pending live price/flow validation.
"""
from datetime import datetime, timezone
import math

CATALYST_MAX_AGE_HOURS=24
QUOTE_MAX_AGE_SECONDS=120
ALLOWED_SOURCES={"official_filing","government","exchange","company_ir","reputable_news"}
ALLOWED_TYPES={"earnings","guidance","contract","regulation","macro","geopolitics","supply_chain"}


def _utc(value):
    if not isinstance(value,str):
        return None
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,OverflowError):
        return None


def verified_catalysts(events, *, now=None):
    now=now or datetime.now(timezone.utc)
    result=[]
    seen=set()
    for e in events:
        if not isinstance(e,dict):
            continue
        stamp=_utc(e.get("published_utc"))
        source=e.get("source_type")
        typ=e.get("event_type")
        sector=e.get("sector")
        uri=e.get("source_url")
        impact=e.get("direction")
        if (stamp is None or source not in ALLOWED_SOURCES or
            typ not in ALLOWED_TYPES or not isinstance(sector,str) or not sector.strip()
            or not isinstance(uri,str) or not uri.startswith("https://") or
            e.get("verified") is not True or impact not in ("positive","negative","uncertain")):
            continue
        age=(now-stamp).total_seconds()
        if not 0<=age<=CATALYST_MAX_AGE_HOURS*3600:
            continue
        key=(uri,sector,typ)
        if key in seen:
            continue
        seen.add(key)
        result.append({**e,"published_utc":stamp.isoformat()})
    return result


def sector_catalyst_ranks(events, *, now=None):
    groups={}
    for e in verified_catalysts(events,now=now):
        sector=e["sector"].strip()
        # Negative and uncertain geopolitical news must never be automatically
        # treated as a bullish catalyst.
        if e["direction"]!="positive":
            continue
        weight={"official_filing":3,"government":3,"exchange":3,
                "company_ir":2,"reputable_news":1}[e["source_type"]]
        g=groups.setdefault(sector,{"sector":sector,"catalyst_score":0,"evidence":[]})
        g["catalyst_score"]+=weight
        g["evidence"].append(e["source_url"])
    return sorted(groups.values(),key=lambda x:x["catalyst_score"],reverse=True)


def rank_sector_leaders(events,quotes,*,now=None,limit=3):
    """Rank candidates only with verified catalyst and market evidence.

    quotes fields: sector, symbol, quote_received_utc, price, turnover,
    turnover_ratio, relative_strength_pct, volume_ratio, spread_pct,
    flow_verified. Ratio baselines must be separately measured, not inferred.
    """
    now=now or datetime.now(timezone.utc)
    sectors={s["sector"]:s for s in sector_catalyst_ranks(events,now=now)}
    result=[]
    for q in quotes:
        if not isinstance(q,dict) or q.get("sector") not in sectors:
            continue
        stamp=_utc(q.get("quote_received_utc"))
        if stamp is None or not 0<=(now-stamp).total_seconds()<=QUOTE_MAX_AGE_SECONDS:
            continue
        try:
            price=float(q["price"])
            turnover=float(q["turnover"])
            turnover_ratio=float(q["turnover_ratio"])
            relative=float(q["relative_strength_pct"])
            volume_ratio=float(q["volume_ratio"])
            spread=float(q["spread_pct"])
            if not all(math.isfinite(v) for v in (price,turnover,turnover_ratio,relative,volume_ratio,spread)):
                continue
            if not (price>0 and turnover>0 and turnover_ratio>=1.2
                    and relative>0 and volume_ratio>=1.2 and 0<=spread<=1.0):
                continue
            if not isinstance(q.get("symbol"),str) or not q["symbol"].strip():
                continue
            # No real-time investor/program inference. Flow is an independent gate.
            flow=q.get("flow_verified") is True
            score=min(100,20+min(sectors[q["sector"]]["catalyst_score"],9)*5
                      +min(turnover_ratio,3)*8+min(volume_ratio,3)*6
                      +min(relative,5)*3+(10 if flow else 0))
            result.append({"sector":q["sector"],"symbol":q["symbol"],
                           "price":price,"score":round(score,1),
                           "flow_verified":flow,"evidence":sectors[q["sector"]]["evidence"],
                           "status":"WATCH · live flow confirmed" if flow else
                                    "WATCH · flow unverified",
                           "quote_received_utc":stamp.isoformat()})
        except (KeyError,ValueError,TypeError,OverflowError):
            continue
    return sorted(result,key=lambda x:x["score"],reverse=True)[:limit]
