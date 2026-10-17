from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_compact_dashboard_renders_without_credentials():
    p=Path(__file__).with_name("atlas_compact_smoke.py")
    app=AppTest.from_file(str(p),default_timeout=20).run()
    assert not app.exception
    assert any("ATLAS 실시간 시장판" in h.value for h in app.markdown)
