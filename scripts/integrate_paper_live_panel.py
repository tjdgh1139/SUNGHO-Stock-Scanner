"""Insert automatic paper-only panel after the live KR/US candidate board."""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
anchor="""render_auto_candidate_board(listing,kis_quote,kis_us_movers,kis_configured,
                            live_tape,websocket_capability,secret_value)"""
added="""from atlas_paper_live_panel import render_paper_live_panel
render_paper_live_panel(live_tape)"""
if "render_paper_live_panel(live_tape)" in s:
    print("Already integrated")
elif s.count(anchor)!=1:
    raise SystemExit("Auto-candidate panel anchor missing or ambiguous")
else:
    s=s.replace(anchor,anchor+"\n"+added,1)
    p.write_text(s,encoding="utf-8")
    print("Integrated automatic paper-only panel")
