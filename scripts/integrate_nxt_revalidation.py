"""Upgrade existing pre-open tracker to NXT-aware, authenticated source gating."""
from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
old="render_preopen_tracker(kis_quote,kis_us_quote,US_SYMBOLS,live_tape)"
new="""render_preopen_tracker(kis_quote,kis_us_quote,US_SYMBOLS,live_tape,
                       websocket_capability,kis_configured,secret_value)"""
if new in s:
    print("NXT integration already present")
elif s.count(old)!=1:
    raise SystemExit("Expected exactly one existing tracker call")
else:
    p.write_text(s.replace(old,new,1),encoding="utf-8")
    print("NXT-aware preopen tracker integrated")
