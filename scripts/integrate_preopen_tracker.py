"""Integrate pre-open snapshot capture and opening-minute tracker safely."""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
marker="from atlas_auto_candidate_board import render_auto_candidate_board"
insert="""from atlas_preopen_tracker_panel import capture_preopen, render_preopen_tracker
render_preopen_tracker(kis_quote,kis_us_quote,US_SYMBOLS,live_tape)
"""
kr_anchor="            st.session_state.scan = result"
us_anchor="                st.session_state.us_scan=run_us_scan(us_symbols,min_score,us_extra_map)"
kr_call="            capture_preopen(result,\"KR\")"
us_call="                capture_preopen(st.session_state.us_scan,\"US\")"
if "render_preopen_tracker(" not in s:
    if s.count(marker)!=1:
        raise SystemExit("Cannot identify unique auto board anchor")
    s=s.replace(marker,insert+marker,1)
if kr_call not in s:
    if s.count(kr_anchor)!=1:
        raise SystemExit("Cannot identify unique manual KR scan assignment")
    s=s.replace(kr_anchor,kr_anchor+"\n"+kr_call,1)
if us_call not in s:
    if s.count(us_anchor)!=1:
        raise SystemExit("Cannot identify unique manual US scan assignment")
    s=s.replace(us_anchor,us_anchor+"\n"+us_call,1)
p.write_text(s,encoding="utf-8")
print("Preopen tracker integrated and manual scan snapshot capture enabled")
