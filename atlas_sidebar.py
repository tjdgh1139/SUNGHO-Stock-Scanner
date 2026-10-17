"""Inline ATLAS monitor embedded in the existing scanner sidebar.

Read-only KIS REST quotes. Never claim WS/foreign/institution confirmation.
"""
from datetime import datetime, timezone
import time
import streamlit as st
from atlas_kis_readonly import WATCHLIST, QuoteUnavailable, token_request, quote_request


@st.cache_data(ttl=3300, show_spinner=False)
def _token(key, secret):
    return token_request(key, secret)


def render_atlas_sidebar():
    with st.expander("📈 ATLAS 실시간 시세 점검", expanded=False):
        st.caption("KIS REST 조회 · 3종목 · 수신 시각 표시 · 주문 없음")
        if not st.button("🔄 삼성전자·하이닉스·삼성전기 조회", key="atlas_sidebar_poll"):
            return
        try:
            key = st.secrets.get("KIS_APP_KEY", "")
            secret = st.secrets.get("KIS_APP_SECRET", "")
        except Exception:
            key, secret = "", ""
        if not key or not secret:
            st.error("KIS 키 미설정: Streamlit Secrets를 확인하세요.")
            return
        try:
            token = _token(key, secret)
        except QuoteUnavailable as exc:
            st.error(str(exc))
            return
        for idx, (code, name) in enumerate(WATCHLIST):
            if idx:
                time.sleep(0.4)
            try:
                quote = quote_request(code, key, secret, token, market="J")
                st.metric(name, f"{quote['현재가']:,.0f}원", f"{quote['등락%']:+.2f}%")
                st.caption(
                    f"거래량 {quote['누적거래량']:,.0f}주 · "
                    f"거래대금 {quote['누적거래대금']/1e8:,.1f}억원"
                )
                st.caption(f"KIS REST 수신 UTC {quote['rest_received_utc']}")
            except QuoteUnavailable as exc:
                st.warning(f"{name}: {exc}")
        st.info("REST 수신 시각은 거래소 체결 시각이 아닙니다. 외국인·기관·프로그램 수급과 BUY 신호는 미검증입니다.")
