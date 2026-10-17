"""KIS WebSocket live tape controls for the existing ATLAS app.

Reuse the app's ONE KISLiveTape session; never create a second connection.
Only an acknowledged, recent trade/book/program snapshot is shown as verified.
"""
from datetime import datetime, timezone
import streamlit as st

STOCKS = {"005930":"삼성전자","000660":"SK하이닉스","009150":"삼성전기"}
REQUIRED = ("trade_received_utc","book_received_utc","program_received_utc")


def live_state(row, connected, now=None):
    now = now or datetime.now(timezone.utc)
    if not connected:
        return "미연결"
    if not row or any(not row.get(k) for k in REQUIRED):
        return "수신 대기 · 일부 채널 누락"
    try:
        age = []
        for k in REQUIRED:
            t = datetime.fromisoformat(str(row[k]).replace("Z","+00:00"))
            if t.tzinfo is None:
                return "시간 정보 미검증"
            age.append((now-t.astimezone(timezone.utc)).total_seconds())
        if any(a<0 or a>10 for a in age):
            return "지연/오래된 수신"
        if row.get("quote_market") != "J":
            return "시장 출처 미확인"
        if row.get("market_date") != now.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Seoul")).strftime("%Y%m%d"):
            return "거래일 불일치"
        return "실시간 수신 확인"
    except (TypeError,ValueError,OverflowError):
        return "시간 정보 미검증"


def render_ws_panel(tape_factory, websocket_capability, kis_configured, secret_value):
    with st.expander("⚡ KIS 실시간 체결·호가·프로그램",expanded=False):
        st.caption("기존 KIS 단일 WebSocket 재사용 · KRX 정규장 · 주문 없음")
        if not websocket_capability() or not kis_configured():
            st.warning("KIS 실시간 접속 준비 미완료")
            return
        tape = tape_factory()
        a,b=st.columns(2)
        if a.button("▶ 3종목 실시간 시작",key="atlas_ws_start"):
            tape.start(tuple(STOCKS),secret_value("KIS_APP_KEY"),
                       secret_value("KIS_APP_SECRET"),market="J")
            st.session_state.atlas_ws_show=True
        if b.button("■ 실시간 중지",key="atlas_ws_stop"):
            tape.stop()
            st.session_state.atlas_ws_show=False
        active=st.session_state.get("atlas_ws_show",False)

        @st.fragment(run_every="2s" if active else None)
        def display():
            rows, connected, error=tape.snapshots()
            st.caption("연결 상태: "+("WebSocket 연결" if connected else "미연결")+
                       (" · "+str(error)[:100] if error else ""))
            for code,name in STOCKS.items():
                row=rows.get(code,{})
                state=live_state(row,connected)
                if state=="실시간 수신 확인":
                    st.success(f"{name}: {row.get('현재가',0):,.0f}원 · 체결강도 {row.get('체결강도',0):,.1f} · 프로그램 {row.get('프로그램순매수대금',0):,.0f} · {state}")
                else:
                    st.caption(f"{name}: {state}")
            st.caption("프로그램 매매 ≠ 외국인·기관 수급. 모든 채널 10초 이내 수신 및 거래일 확인 전에는 LIVE 표시 안 함.")
        display()
