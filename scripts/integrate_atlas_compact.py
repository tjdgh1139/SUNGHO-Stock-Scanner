"""Place the compact overview above the editorial hero, without rewriting app logic."""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
marker='st.markdown(\'<div class="scanner-hero scanner-editorial"'
insert='from atlas_compact_dashboard import render_compact_dashboard\nrender_compact_dashboard(live_tape, websocket_capability, kis_configured, secret_value)\n\n'
if "render_compact_dashboard(live_tape" in s:
    print("Already integrated")
elif s.count(marker)!=1:
    raise SystemExit("Expected unique scanner hero marker")
else:
    s=s.replace(marker,insert+marker,1)
    p.write_text(s,encoding="utf-8")
    print("Compact ATLAS overview added before hero")
