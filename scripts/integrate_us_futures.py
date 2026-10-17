"""Integrate delayed US futures provider into existing macro snapshot.

Idempotent; preserve domestic index/futures sources and other macro indicators.
"""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
old='    live=kis_index_snapshot()+[domestic_future_snapshot(),night_future_snapshot()]'
new='''    live=kis_index_snapshot()+[domestic_future_snapshot(),night_future_snapshot()]
    # US continuous futures are public delayed quotes, not authenticated live ticks.
    try:
        from futures_quotes import futures_snapshot
        live.extend(cached_us_futures_snapshot())
    except Exception:
        pass'''
helper='''@st.cache_data(ttl=60,show_spinner=False)
def cached_us_futures_snapshot():
    from futures_quotes import futures_snapshot
    return futures_snapshot()

'''
if "live.extend(cached_us_futures_snapshot())" in s:
    print("Already integrated")
elif s.count(old)!=1 or s.count("def macro_snapshot():")!=1:
    raise SystemExit("Expected macro snapshot anchors missing or ambiguous")
else:
    s=s.replace("def macro_snapshot():",helper+"def macro_snapshot():",1)
    s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")
    print("Added delayed US futures to macro panel")
