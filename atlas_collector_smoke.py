"""ATLAS collector staging smoke test with synthetic quotes only.

No credentials, network access, live orders or production database changes.
"""
import json
import tempfile
from pathlib import Path
from atlas_cycle_coordinator import run_cycle
from atlas_collector_heartbeat import latest_heartbeat
from atlas_market_quote_store import latest_quote

def run_smoke() -> dict:
    with tempfile.TemporaryDirectory(prefix="atlas_smoke_") as folder:
        root=Path(folder)
        market=str(root/"market.sqlite")
        health=str(root/"health.sqlite")
        def provider(symbol):
            return {"price":1292000 if symbol=="000660" else 234000,
                    "volume":1000,"turnover":1000000}
        result=run_cycle(market,["000660","005930"],provider,
                         received_at_utc="2026-10-20T09:00:00Z",
                         heartbeat_db_path=health,market="KRX",
                         heartbeat_at_utc="2026-10-20T09:00:01Z")
        quotes=[latest_quote(market,"KRX",symbol) for symbol in ("000660","005930")]
        heartbeat=latest_heartbeat(health,"KRX")
        passed=(result.health.state=="HEALTHY" and result.result.stored==2
                and all(q and q["price"]>0 for q in quotes)
                and heartbeat and heartbeat["state"]=="HEALTHY")
        return {"result":"PASS" if passed else "FAIL","stored":result.result.stored,
                "health":result.health.state,"heartbeat":heartbeat["state"] if heartbeat else None}

if __name__=="__main__":
    report=run_smoke()
    print(json.dumps(report))
    raise SystemExit(0 if report["result"]=="PASS" else 1)
