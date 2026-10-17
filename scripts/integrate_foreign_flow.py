"""Embed KIS confirmed foreign flow candidate ranking into existing app."""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
needle='render_compact_dashboard(live_tape, websocket_capability, kis_configured, secret_value)'
added='''from atlas_foreign_flow_panel import render_foreign_flow_panel
render_foreign_flow_panel(st.session_state.get("scan",pd.DataFrame()),live_tape,secret_value)'''
if "render_foreign_flow_panel(" in s:
    print("Already integrated")
elif s.count(needle)!=1:
    raise SystemExit("Compact dashboard anchor missing or ambiguous")
else:
    s=s.replace(needle,needle+"\n"+added,1)
    p.write_text(s,encoding="utf-8")
    print("Integrated foreign flow ranking")
