"""Insert autonomous KR/US momentum panels before manual scanner controls."""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
anchor='render_foreign_flow_panel(st.session_state.get("scan",pd.DataFrame()),live_tape,secret_value)'
added='''from atlas_auto_candidate_board import render_auto_candidate_board
render_auto_candidate_board(listing,kis_quote,kis_us_movers,kis_configured,\n                            live_tape,websocket_capability,secret_value)'''
if "render_auto_candidate_board(" in s:
    print("Already integrated")
elif s.count(anchor)!=1:
    raise SystemExit("Unique foreign-flow panel anchor missing")
else:
    s=s.replace(anchor,anchor+"\n"+added,1)
    p.write_text(s,encoding="utf-8")
    print("Autonomous KR/US candidate board inserted above manual scanner")
