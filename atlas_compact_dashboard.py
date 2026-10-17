"""ATLAS compact, readable market overview for existing Streamlit app.

WebSocket display refresh: 2s while page open. KIS REST fallback: at most
once per 15s during KRX weekday session. REST is never labeled tick-live.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import time
import streamlit as st
from atlas_kis_readonly import WATCHLIST, QuoteUnavailable, quote_request, token_request
from atlas_sidebar import krx_regular_open
from atlas_ws_panel import live_state
from market_indicators import get_indicator

KST=ZoneInfo("Asia/Seoul")
PT=ZoneInfo("America/Los_Angeles")
REST_SECONDS=15
SCREEN_SECONDS=2
QUICK=("미국 변동성 VIX","필라델피아 반도체 SOX","달러지수 DXY",
       "달러/원 USDKRW","반도체 3배 ETF SOXL")


@st.cache_data(ttl=3300,show_spinner=False)
def _token(key,secret):
    return token_request(key,secret)


@st.cache_data(ttl=120,show_spinner=False)
def _quick_macro():
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as pool:
        return list(pool.map(get_indicator,QUICK))


def compact_rows(rest_rows, ws_rows, connected, now=None):
    now=now or datetime.now(timezone.utc)
    output=[]
    for code,name in WATCHLIST:
        live=ws_rows.get(code,{})
        state=live_state(live,connected,now)
        if state=="실시간 수신 확인" and float(live.get("현재가") or 0)>0:
            output.append({"code":code,"name":name,"price":float(live["현재가"]),
                           "change":live.get("등락%"),"state":"LIVE · KIS WS",
                           "volume":live.get("누적거래량"),
                           "strength":live.get("체결강도"),"age":0})
            continue
        rest=rest_rows.get(code,{})
        if float(rest.get("현재가") or 0)>0:
            output.append({"code":code,"name":name,"price":float(rest["현재가"]),
                           "change":rest.get("등락%"),"state":"REST · 지연 가능",
                           "volume":rest.get("누적거래량"),"strength":None,"age":None})
        else:
            output.append({"code":code,"name":name,"price":None,"change":None,
                           "state":"시세 미수신","volume":None,"strength":None,"age":None})
    return output


def render_compact_dashboard(tape_factory, websocket_capability, kis_configured, secret_value):
    st.markdown("### ⚡ ATLAS 실시간 시장판")
    now=datetime.now(timezone.utc)
    st.caption(f"한국 {now.astimezone(KST):%m/%d %H:%M:%S} KST  ·  미국 서부 {now.astimezone(PT):%m/%d %H:%M:%S} PT")
    c1,c2,c3=st.columns([1.2,1,1])
    enabled=c1.toggle("장중 자동 감시",value=True,key="atlas_compact_auto")
    tape=tape_factory()
    if c2.button("▶ 실시간 연결",use_container_width=True,key="atlas_compact_ws_start"):
        if websocket_capability() and kis_configured() and krx_regular_open():
            tape.start(tuple(code for code,_ in WATCHLIST),secret_value("KIS_APP_KEY"),
                       secret_value("KIS_APP_SECRET"),market="J")
        else:
            st.warning("정규장 또는 KIS WebSocket 준비 상태를 확인하세요.")
    if c3.button("■ 연결 중지",use_container_width=True,key="atlas_compact_ws_stop"):
        tape.stop()
    if "atlas_compact_rest" not in st.session_state:
        st.session_state.atlas_compact_rest={}
    if "atlas_compact_poll" not in st.session_state:
        st.session_state.atlas_compact_poll=0.0

    @st.fragment(run_every=f"{SCREEN_SECONDS}s" if enabled else None)
    def board():
        open_now=krx_regular_open()
        # Session-scoped REST polling, not a claim of streaming market data.
        if enabled and open_now and kis_configured() and (
            time.monotonic()-st.session_state.atlas_compact_poll>=REST_SECONDS
            or st.session_state.atlas_compact_poll==0
        ):
            st.session_state.atlas_compact_poll=time.monotonic()
            try:
                key=secret_value("KIS_APP_KEY")
                secret=secret_value("KIS_APP_SECRET")
                token=_token(key,secret)
                for i,(code,_) in enumerate(WATCHLIST):
                    if i:time.sleep(0.35)
                    try:
                        st.session_state.atlas_compact_rest[code]=quote_request(
                            code,key,secret,token,market="J")
                    except QuoteUnavailable:
                        pass
            except (QuoteUnavailable,KeyError,ValueError):
                pass
        ws_rows,connected,error=tape.snapshots()
        data=compact_rows(st.session_state.atlas_compact_rest,ws_rows,connected)
        cols=st.columns(3,gap="small")
        for col,row in zip(cols,data):
            with col:
                with st.container(border=True):
                    st.markdown("**"+row["name"]+"**")
                    price="—" if row["price"] is None else f"{row['price']:,.0f}원"
                    pct=row["change"]
                    delta=None if pct is None else f"{float(pct):+.2f}%"
                    st.metric("현재가",price,delta,delta_color="normal")
                    st.caption(row["state"])
                    if row["volume"] is not None:
                        st.caption(f"거래량 {float(row['volume']):,.0f}주")
                    if row["strength"] is not None:
                        st.caption(f"체결강도 {float(row['strength']):.1f}")
        if not open_now:
            st.caption("KRX 정규장 시간 외 · 마지막 시세는 실시간이 아닙니다. 휴장일은 별도 확인 필요.")
        elif not connected:
            st.caption("KIS WS 미연결 · REST는 15초 간격 조회, 실시간 체결 아님")
        if error:
            st.caption("실시간 연결 상태: "+str(error)[:90])
    board()

    with st.expander("🌎 핵심 글로벌 지표 한눈에 보기",expanded=True):
        if st.button("글로벌 지표 조회/갱신",key="atlas_compact_macro_button"):
            _quick_macro.clear()
        rows=_quick_macro()
        cols=st.columns(5,gap="small")
        for col,r in zip(cols,rows):
            with col:
                val=r.get("최근값")
                st.metric(r["지표"].replace("필라델피아 반도체 ","").replace("미국 변동성 ",""),
                          f"{float(val):,.2f}" if val is not None else "—",
                          f"{r['전일대비%']:+.2f}%" if r.get("전일대비%") is not None else None)
                st.caption("지연 가능" if val is not None else "미수신")
        st.caption("글로벌 공개 시세는 실시간 인증 데이터가 아니며 공급자 기준 시각은 상세 패널에서 확인하세요.")
