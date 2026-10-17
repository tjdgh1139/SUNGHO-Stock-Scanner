"""Ensure ATLAS monitor is reachable from the existing custom sidebar.

Idempotent source patch. Does not change the scanner's business logic.
"""
from pathlib import Path

app = Path("app.py")
source = app.read_text(encoding="utf-8")
needle = "with st.sidebar:"
marker = 'st.page_link("pages/01_ATLAS_Live_Monitor.py", label="📈 ATLAS Live Monitor")'
if marker in source:
    print("ATLAS sidebar link already present")
elif source.count(needle) != 1:
    raise SystemExit("Cannot safely identify unique sidebar block")
else:
    source = source.replace(needle, needle + "\n    " + marker, 1)
    app.write_text(source, encoding="utf-8")
    print("ATLAS sidebar link inserted")
