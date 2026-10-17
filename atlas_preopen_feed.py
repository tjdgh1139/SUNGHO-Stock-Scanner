"""Read verified 07:00 and 07:55 pre-NXT candidate snapshots; never fabricate."""
import json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST=ZoneInfo("Asia/Seoul")

def read_snapshot(path="data/atlas_preopen_candidates.json", now=None):
    now=now or datetime.now(timezone.utc)
    try:
        p=json.loads(Path(path).read_text(encoding="utf-8"))
        t=datetime.fromisoformat(p["generated_at_utc"].replace("Z","+00:00"))
        if t.tzinfo is None or p.get("market")!="KR" or p.get("stage") not in ("first_0700","refresh_0755"):
            return None
        local=now.astimezone(KST)
        if local.weekday()>4 or p.get("session_date")!=local.strftime("%Y%m%d"):
            return None
        if t.astimezone(KST).strftime("%Y%m%d")!=p["session_date"]:
            return None
        minute=t.astimezone(KST).hour*60+t.astimezone(KST).minute
        if p["stage"]=="first_0700" and not 420<=minute<475:
            return None
        if p["stage"]=="refresh_0755" and not 475<=minute<530:
            return None
        if not 0<=(now-t).total_seconds()<=3*3600:
            return None
        items=p["candidates"]
        if not isinstance(items,list) or len(items)>5:
            return None
        for c in items:
            if not isinstance(c,dict) or not isinstance(c.get("symbol"),str) or len(c["symbol"])!=6:
                return None
            if not isinstance(c.get("source_urls"),list) or not c["source_urls"]:
                return None
            if any(not isinstance(u,str) or not u.startswith("https://") for u in c["source_urls"]):
                return None
            if not 0<=float(c["score"])<=100:
                return None
        return p
    except (OSError,KeyError,TypeError,ValueError,OverflowError):
        return None
