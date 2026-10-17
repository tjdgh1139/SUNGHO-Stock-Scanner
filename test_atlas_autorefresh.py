from datetime import datetime, timezone
from atlas_sidebar import krx_regular_open, POLL_SECONDS

def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def test_krx_open_during_weekday_session():
    assert krx_regular_open(utc("2026-10-16T01:00:00Z"))

def test_krx_closed_on_saturday():
    assert not krx_regular_open(utc("2026-10-17T01:00:00Z"))

def test_krx_closed_before_open():
    assert not krx_regular_open(utc("2026-10-15T23:59:00Z"))

def test_krx_closed_after_close():
    assert not krx_regular_open(utc("2026-10-16T06:30:00Z"))

def test_refresh_interval():
    assert POLL_SECONDS == 15

def test_sidebar_streamlit_smoke_no_secrets():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from unittest.mock import patch
    import streamlit as st
    # The page must render without credentials, even on market-closed days.
    script = Path(__file__).with_name("atlas_sidebar_smoke.py")
    app = AppTest.from_file(str(script), default_timeout=20).run()
    assert not app.exception
