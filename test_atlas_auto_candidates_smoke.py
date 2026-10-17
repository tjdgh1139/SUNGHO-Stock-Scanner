from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_auto_candidate_board_without_kis_fails_closed():
    path=Path(__file__).with_name("atlas_auto_candidates_smoke.py")
    app=AppTest.from_file(str(path),default_timeout=20).run()
    assert not app.exception
    assert any("KIS API 연결이 필요합니다" in x.value for x in app.warning)
