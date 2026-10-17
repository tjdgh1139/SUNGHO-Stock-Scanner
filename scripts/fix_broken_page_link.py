from pathlib import Path
p=Path("app.py")
s=p.read_text(encoding="utf-8")
old='st.page_link("pages/01_ATLAS_Live_Monitor.py", label="📈 ATLAS Live Monitor")'
new='st.caption("📈 ATLAS Live Monitor: 배포 페이지 확인 중 (기존 스캔 정상 사용 가능)")'
if old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding="utf-8")
    print("Removed broken Streamlit page link")
elif new in s:
    print("Already patched")
else:
    raise SystemExit("Expected sidebar link not found")
