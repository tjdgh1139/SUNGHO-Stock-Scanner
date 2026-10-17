"""Embed the working ATLAS KIS quote monitor in the existing app sidebar.

Idempotent and fail-closed; the previous Streamlit multipage link is not used.
"""
from pathlib import Path
p = Path("app.py")
s = p.read_text(encoding="utf-8")
needle = "with st.sidebar:"
call = "    from atlas_sidebar import render_atlas_sidebar\n    render_atlas_sidebar()"
old = '    st.caption("📈 ATLAS Live Monitor: 배포 페이지 확인 중 (기존 스캔 정상 사용 가능)")\n'
if s.count(needle) != 1:
    raise SystemExit("Expected exactly one existing sidebar block")
if "render_atlas_sidebar()" in s:
    print("Already embedded")
else:
    s = s.replace(needle, needle + "\n" + call, 1)
    s = s.replace(old, "")
    p.write_text(s, encoding="utf-8")
    print("Embedded ATLAS sidebar monitor")
