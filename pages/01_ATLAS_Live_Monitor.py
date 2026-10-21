"""ATLAS multipage monitor. Safe read-only integration, no broker orders."""
from datetime import datetime, timezone
import time
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from atlas_kis_readonly import WATCHLIST, QuoteUnavailable, token_request, quote_request
from atlas_safe_flow import evaluate_safe_flow

st.set_page_config(page_title="ATLAS | 실시간 수급 점검", page_icon="📈", layout="wide")
st.title("📈 ATLAS · KIS 장중 감시")
st.caption("읽기 전용 · KIS REST 수신 시각 표시 · 실시간 체결/호가/프로그램 검증 전 매수 신호 금지")

try:
    key = st.secrets.get("KIS_APP_KEY", "")
    secret = st.secrets.get("KIS_APP_SECRET", "")
except Exception:
    key, secret = "", ""

if not key or not secret:
    st.error("KIS 인증정보 미설정. Streamlit Secrets에 KIS_APP_KEY와 KIS_APP_SECRET이 필요합니다.")
    st.stop()

@st.cache_data(ttl=3300, show_spinner=False)
def cached_token(k, s):
    return token_request(k, s)

market = st.selectbox("시장 구분", ["J", "UN", "NX"], index=0,
                      format_func=lambda x: {"J":"KRX (J)", "UN":"통합 (UN) — 검증 필요",
                                             "NX":"NXT (NX) — 검증 필요"}[x])
auto = st.toggle("30초 간격 자동 갱신", value=False,
                 help="KIS REST API 사용량에 주의하세요. 실시간 WebSocket 체결 감시는 아닙니다.")
if auto:
    st_autorefresh(interval=30_000, key="atlas_rest_refresh")

if "atlas_last_quotes" not in st.session_state:
    st.session_state.atlas_last_quotes = {}
if "atlas_last_poll" not in st.session_state:
    st.session_state.atlas_last_poll = 0.0

refresh = st.button("🔄 지금 시세 확인", type="primary") or auto
if refresh and time.monotonic() - st.session_state.atlas_last_poll >= 12:
    st.session_state.atlas_last_poll = time.monotonic()
    try:
        token = cached_token(key, secret)
        for i, (code, name) in enumerate(WATCHLIST):
            if i:
                time.sleep(0.4)
            try:
                row = quote_request(code, key, secret, token, market=market)
                identity = market + ":" + code
                previous = st.session_state.atlas_last_quotes.get(identity)
                st.session_state.atlas_last_quotes[identity] = row
                st.session_state["atlas_delta_" + identity] = (
                    max(0.0, row["누적거래대금"] - previous["누적거래대금"])
                    if previous and row["누적거래대금"] >= previous["누적거래대금"] else None
                )
                # REST lacks authenticated trade strength, program flow and exchange trade timestamps.
                # Call the integrated evaluator: it must fail closed rather than invent a BUY.
                st.session_state["atlas_signal_" + identity] = (
                    evaluate_safe_flow(previous, row, now=datetime.now(timezone.utc))
                    if previous else {"signal":"WAIT","reason":"first_snapshot"}
                )
            except QuoteUnavailable as exc:
                st.warning(f"{name}: {exc}")
    except QuoteUnavailable as exc:
        st.error(str(exc))
elif refresh:
    st.info("요청 간격 보호: 최소 12초 이후 다시 갱신할 수 있습니다.")

st.divider()
for code, name in WATCHLIST:
    identity = market + ":" + code
    row = st.session_state.atlas_last_quotes.get(identity)
    st.subheader(name + " (" + code + ")")
    if not row:
        st.info("아직 이 시장의 인증 시세가 없습니다.")
        continue
    cols = st.columns(4)
    cols[0].metric("현재가", f"{row['현재가']:,.0f}원", f"{row['등락%']:+.2f}%")
    cols[1].metric("누적 거래량", f"{row['누적거래량']:,.0f}주")
    cols[2].metric("누적 거래대금", f"{row['누적거래대금']/1e8:,.1f}억원")
    delta = st.session_state.get("atlas_delta_" + identity)
    cols[3].metric("직전 조회 이후 거래대금", "미확인" if delta is None else f"{delta/1e8:,.2f}억원")
    st.caption("수신(UTC): " + row["rest_received_utc"] +
               " · " + row["source"] + " · REST 수신 시각이며 거래소 체결 시각 아님")
    signal = st.session_state.get("atlas_signal_" + identity, {"signal":"WAIT"})
    st.warning("매수세 최종 판정: " + signal["signal"] +
               " · WS 체결강도·프로그램 순매수·동시간대 기준 거래대금 미검증")
st.divider()
st.info("외국인/기관 순매매는 프로그램 매매와 다릅니다. 검증된 별도 공급자 없이는 표시하지 않습니다. "
        "이 화면은 주문을 실행하지 않으며, 매수/매도 추천이 아닙니다.")
