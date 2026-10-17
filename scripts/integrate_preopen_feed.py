from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
anchor="from atlas_preopen_tracker_panel import capture_preopen, render_preopen_tracker"
insert="from atlas_preopen_feed_panel import render_published_preopen\nrender_published_preopen()\n"
if "render_published_preopen()" in s:
    print("Already integrated")
elif s.count(anchor)!=1:
    raise SystemExit("Preopen tracker anchor missing or ambiguous")
else:
    p.write_text(s.replace(anchor,insert+anchor,1),encoding="utf-8")
    print("Published pre-NXT candidate feed added above A tracker")
