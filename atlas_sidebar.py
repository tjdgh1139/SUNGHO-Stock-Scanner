"""ATLAS read-only KIS REST monitor with session-scoped 30-second auto refresh.

This is polling, NOT tick-by-tick WebSocket. Only refresh while the page is open.
Never label REST receipt timestamps as exchange execution timestamps.
"""
from datetime import datetime, time as clock_time, timezone
from zoneinfo import ZoneInfo
import time
import streamlit as st
from atlas_kis_readonly import WATCHLIST, QuoteUnavailable, token_request, quote_request

KST = ZoneInfo("Asia/Seoul")
POLL_SECONDS = 30


def krx_regular_open(now=None):
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(KST)
    return local.weekday() < 5 and clock_time(9, 0) <= local.time() < clock_time(15, 30)


@st.cache_data(ttl=3300, show_spinner=False)
def _token(key, secret):
    return token_request(key, secret)


def _render_quotes(rows, updated=None):
    for code, name in WATCHLIST:
        quote = rows.get(code)
        if not quote:
            st.caption(f"{name}: 수신된 시세 없음")
            continue
        st.metric(name, f"{quote['현재가']:,.0f}원", f"{quote['등락%']:+.2f}%")
        st.caption(f"거래량 {quote['누적거래량']:,.0f}주 · "
                   f"거래대금 {quote['누적거래대금']/1e8:,.1f}억원")
        st.caption(f"KIS REST 수신 UTC {quote['rest_received_utc']}")
    if updated:
        st.caption(f"마지막 REST 조회 UTC: {updated.isoformat()}")
    st.info("30초 REST 조회는 틱 단위 실시간 체결이 아닙니다. "
            "외국인·기관·프로그램 수급 및 BUY 신호는 검증 전입니다.")


def render_atlas_sidebar():
    with st.expander("📈 ATLAS 시세 자동 점검", expanded=False):
        now = datetime.now(timezone.utc)
        open_now = krx_regular_open(now)
        st.caption("KIS REST · 3종목 · 주문 없음 · KRX 정규장 기준")
        if open_now:
            st.success("한국 KRX 정규장 시간대 · 휴장일은 별도 검증 필요")
        else:
            st.warning("KRX 정규장 시간 외 · 표시되는 가격은 마지막 조회값일 수 있음")
        auto = st.toggle("30초 자동 갱신 (이 페이지가 열려 있을 때만)",
                         value=False, key="atlas_auto_poll")
        if auto and not open_now:
            st.caption("정규장 시간 외 자동 조회는 중단됩니다.")
        if "atlas_sidebar_quotes" not in st.session_state:
            st.session_state.atlas_sidebar_quotes = {}
        if "atlas_sidebar_last_request" not in st.session_state:
            st.session_state.atlas_sidebar_last_request = 0.0

        @st.fragment(run_every=f"{POLL_SECONDS}s" if auto and open_now else None)
        def monitor():
            manual = st.button("🔄 3종목 지금 조회", key="atlas_sidebar_poll")
            should_poll = manual or (auto and krx_regular_open())
            if should_poll:
                # Protect against repeated reruns and avoid excessive API requests.
                elapsed = time.monotonic() - st.session_state.atlas_sidebar_last_request
                if elapsed >= POLL_SECONDS or st.session_state.atlas_sidebar_last_request == 0:
                    st.session_state.atlas_sidebar_last_request = time.monotonic()
                    try:
                        key = st.secrets.get("KIS_APP_KEY", "")
                        secret = st.secrets.get("KIS_APP_SECRET", "")
                    except Exception:
                        key, secret = "", ""
                    if not key or not secret:
                        st.error("KIS 키 미설정: Streamlit Secrets를 확인하세요.")
                    else:
                        try:
                            token = _token(key, secret)
                            for idx, (code, name) in enumerate(WATCHLIST):
                                if idx:
                                    time.sleep(0.4)
                                try:
                                    row = quote_request(code, key, secret, token, market="J")
                                    st.session_state.atlas_sidebar_quotes[code] = row
                                except QuoteUnavailable as exc:
                                    st.warning(f"{name}: {exc}")
                        except QuoteUnavailable as exc:
                            st.error(str(exc))
                elif manual:
                    st.caption("API 호출 제한 보호: 잠시 후 다시 조회하세요.")
            _render_quotes(st.session_state.atlas_sidebar_quotes)
        monitor()
