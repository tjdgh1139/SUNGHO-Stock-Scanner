"""Add the macro and existing KIS WebSocket panels to the scanner sidebar.

Idempotent, exact anchor required. Run regression before publishing.
"""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
needle="    render_atlas_sidebar()"
added="""    from atlas_ws_panel import render_ws_panel
    render_ws_panel(live_tape, websocket_capability, kis_configured, secret_value)
    from atlas_global_panel import render_global_indices
    render_global_indices()"""
if "render_global_indices()" in s and "render_ws_panel(" in s:
    print("Already integrated")
elif s.count(needle)!=1:
    raise SystemExit("Existing sidebar anchor not unique")
else:
    s=s.replace(needle,needle+"\n"+added,1)
    p.write_text(s,encoding="utf-8")
    print("Added global indices and existing KIS WS tape panels")
