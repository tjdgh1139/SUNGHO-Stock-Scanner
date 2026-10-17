"""Scheduled KR preopen screening. No API secrets or orders required.

Uses historical public OHLCV and publishes only validated EOD WATCH candidates.
A full news/catalyst/foreign-flow ranking is NOT implemented here.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import csv,json,sys
import FinanceDataReader as fdr
from atlas_preopen_background import build_snapshot

ROOT=Path(__file__).resolve().parent
UNIVERSE=ROOT/"config/atlas_preopen_universe.csv"
OUTPUT=ROOT/"data/atlas_preopen_kr_latest.json"


def main(now=None):
    now=now or datetime.now(timezone.utc)
    with UNIVERSE.open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f))
    universe=[(r["code"],r["name"],r["sector"]) for r in rows]
    start=(now-timedelta(days=95)).strftime("%Y-%m-%d")
    def load(symbol):
        return fdr.DataReader(symbol,start)
    snapshot=build_snapshot(universe,load,now=now)
    if snapshot is None:
        print("Outside KST 07:00 or 07:55 preopen windows; no publication")
        return 0
    # Preserve previous 1st-phase result if the 2nd phase has no validated data.
    if not snapshot["candidates"]:
        print("No validated EOD candidates; refusing to publish a fabricated TOP5")
        return 0
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(OUTPUT)
    print("Published",snapshot["phase"],"session",snapshot["session_date"],
          "validated",snapshot["coverage"]["validated"],"top",len(snapshot["candidates"]))
    return 0


if __name__=="__main__":
    sys.exit(main())
