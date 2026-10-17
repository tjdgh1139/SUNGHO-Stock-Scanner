"""US Treasury 2/10/30-year yields, official FRED daily observations.

Not live yields; source is Federal Reserve Bank of St. Louis FRED daily series.
"""
from datetime import date,datetime,timezone
from io import StringIO
import csv
import requests

SERIES={"미국 국채 2년":"DGS2","미국 국채 10년":"DGS10","미국 국채 30년":"DGS30"}


def treasury_yields(*, get=requests.get, today=None):
    today=today or datetime.now(timezone.utc).date()
    output=[{"지표":label,"상태":"미수신 · FRED 일별 데이터 실패","단위":"% (연 수익률)","공급자":"FRED"}
            for label in SERIES]
    try:
        r=get("https://fred.stlouisfed.org/graph/fredgraph.csv",
              params={"id":",".join(SERIES.values()),"cosd":str(today.replace(day=1))},
              timeout=8,headers={"User-Agent":"ATLAS/1.0"})
        r.raise_for_status()
        rows=list(csv.DictReader(StringIO(r.text)))
        for item,label in zip(output,SERIES):
            code=SERIES[label]
            valid=[]
            for row in rows:
                try:
                    d=date.fromisoformat(row["observation_date"] if "observation_date" in row else row["DATE"])
                    val=float(row[code])
                    if 0<val<30 and d<=today:
                        valid.append((d,val))
                except (KeyError,TypeError,ValueError):
                    continue
            if valid:
                d,val=max(valid)
                age=(today-d).days
                item.update({"최근값":val,"기준일":d.isoformat(),
                             "상태":"FRED 일별 · 지연" if age<=5 else "과거 일별 자료 · 5일 초과"})
        return output
    except (requests.RequestException,ValueError,TypeError):
        return output
