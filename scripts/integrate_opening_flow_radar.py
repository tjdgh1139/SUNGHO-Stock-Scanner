"""Integrate opening radar above automatic KR/US prediction board."""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
anchor="from atlas_auto_candidate_board import render_auto_candidate_board"
insert="""from atlas_opening_flow_panel import render_opening_flow_panel
render_opening_flow_panel(live_tape)
"""
if "render_opening_flow_panel(live_tape)" in s:
    print("Already integrated")
elif s.count(anchor)!=1:
    raise SystemExit("Cannot identify unique autonomous candidate board anchor")
else:
    s=s.replace(anchor,insert+anchor,1)
    p.write_text(s,encoding="utf-8")
    print("Integrated opening 1/3/5 minute radar")
