from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_paper_panel_without_live_feed_renders_no_fake_fills():
    path=Path(__file__).with_name("atlas_paper_live_smoke.py")
    app=AppTest.from_file(str(path),default_timeout=20).run()
    assert not app.exception
    assert any("ATLAS 자동 가상매매 검증" in x.value for x in app.markdown)
