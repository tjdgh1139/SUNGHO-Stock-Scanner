"""Opening minute 1-5 tracker for pre-open frozen KR and US scan picks.

On-page only; polls each market once per minute during first five minutes.
Frozen candidates are not silently replaced by dynamic discovery candidates.
"""
from datetime import datetime, timezone
import time
import streamlit as st
import pandas as pd
from atlas_preopen_monitor import freeze_candidates,minute_after_open,minute_record
from atlas_nxt_revalidation import market_phase,rerank_preopen_on_nxt


def capture_preopen(frame,market,now=None):
    if frame is None or frame.empty:
        return None
    if "점수" in frame.columns:
        frame=frame.sort_values("점수",ascending=False)
    frozen=freeze_candidates(frame.to_dict("records"),market,now=now)
    if frozen and frozen["candidates"]:
        st.session_state["atlas_frozen_"+market]=frozen
    return frozen


def render_preopen_tracker(kis_quote_fn,kis_us_quote_fn,us_symbols,tape_factory,
                           websocket_capability,kis_configured,secret_value):
    st.markdown("### 📌 A. 장전 스캔 후보 · 개장 1~5분 추적")
    st.caption("장전에 수동 스캔하면 후보가 고정되고, 개장 후 매분 시세·진입/손절/목표를 재평가합니다. 신규 급등 후보는 별도 B 화면에 표시됩니다.")

    @st.fragment(run_every="5s")
    def panel():
        now=datetime.now(timezone.utc)
        for market,label in (("KR","🇰🇷 한국"),("US","🇺🇸 미국")):
            frozen=st.session_state.get("atlas_frozen_"+market)
            with st.expander(label+" · 장전 고정 후보",expanded=True):
                if not frozen or not frozen.get("candidates"):
                    st.info("장전 스캔 결과가 아직 고정되지 않았습니다.")
                    continue
                if market=="KR" and market_phase(now)=="NXT_PRE":
                    st.markdown("**NXT 프리마켓 08:00~08:50 · 장전 후보 즉시 재검증**")
                    tape=tape_factory()
                    # Reuse one KIS tape, never interrupt a running KRX session.
                    if websocket_capability() and kis_configured():
                        last=st.session_state.get("atlas_nxt_last_attempt",-1e12)
                        thread=getattr(tape,"thread",None)
                        active=bool(thread and thread.is_alive())
                        if (not active and time.monotonic()-last>=120 and
                            getattr(tape,"market",None) in (None,"NX")):
                            st.session_state.atlas_nxt_last_attempt=time.monotonic()
                            try:
                                tape.start(tuple(c["symbol"] for c in frozen["candidates"][:5]),
                                           secret_value("KIS_APP_KEY"),
                                           secret_value("KIS_APP_SECRET"),market="NX")
                            except Exception:
                                pass
                    ws,connected,_=tape.snapshots()
                    if connected and getattr(tape,"market",None)=="NX":
                        nxt=rerank_preopen_on_nxt(frozen,ws,now=now,limit=5)
                    else:
                        nxt=[]
                    if nxt:
                        st.dataframe(pd.DataFrame([{
                            "재선정 순위":i,"종목":x["name"],"NXT 가격":x["nxt_price"],
                            "체결강도":x["nxt_strength"],"재평가 점수":x["recheck_score"],
                            "판정":x["status"],"수신 경과(초)":x["nxt_age_seconds"],
                        } for i,x in enumerate(nxt,1)]),hide_index=True,use_container_width=True)
                    else:
                        st.warning("인증된 NXT 실시간 체결 미수신 · KRX 가격으로 대체하지 않습니다.")
                minute=minute_after_open(now,market)
                st.caption("고정 "+frozen["frozen_at_utc"]+" · 후보 "+str(len(frozen["candidates"]))+"종목")
                if minute is None:
                    st.caption("개장 첫 5분 외 시간 · 고정 리스트 보관 중 (이 브라우저 세션)")
                else:
                    statekey="atlas_minute_"+market+"_"+frozen["session_date"]
                    state=st.session_state.get(statekey,{})
                    if minute not in state:
                        quotes={}
                        if market=="KR":
                            ws,connected,_=tape_factory().snapshots()
                        else:
                            ws,connected={},False
                        for item in frozen["candidates"]:
                            symbol=item["symbol"]
                            try:
                                if market=="KR":
                                    w=ws.get(symbol,{}) if connected else {}
                                    if w.get("trade_received_utc") and w.get("현재가"):
                                        quotes[symbol]={**w,"quote_received_utc":w["trade_received_utc"]}
                                    else:
                                        q=kis_quote_fn(symbol,market="J")
                                        if q:
                                            quotes[symbol]={**q,"quote_market":"J"}
                                else:
                                    exchange=us_symbols.get(symbol)
                                    if exchange:
                                        q=kis_us_quote_fn(symbol,exchange)
                                        if q:
                                            quotes[symbol]=q
                            except Exception:
                                continue
                        record=minute_record(frozen,quotes,now=datetime.now(timezone.utc))
                        if record:
                            state[minute]=record
                            st.session_state[statekey]=state
                    st.caption("개장 "+str(minute)+"분차 · "+str(len(state))+"/5분 확인")
                    st.write(" · ".join(("● "+str(m)+"분" if m in state else "○ "+str(m)+"분") for m in range(1,6)))
                    current=state.get(minute) or state.get(max(state)) if state else None
                    if current:
                        st.dataframe(pd.DataFrame([{
                            "종목":x["name"],"현재가":x["price"],
                            "진입 하단":x["entry_low"],"진입 상단":x["entry_high"],
                            "손절 기준":x["stop"],"1차 목표":x["target"],
                            "판정":x["status"],"수신 경과(초)":x["quote_age"],
                        } for x in current["rows"]]),hide_index=True,use_container_width=True)
                        history=[]
                        for m in sorted(state):
                            for x in state[m]["rows"]:
                                history.append({"분":m,"종목":x["name"],
                                                "확인 가격":x["price"],"상태":x["status"]})
                        if history:
                            with st.expander("1~5분 판단 기록",expanded=False):
                                st.dataframe(pd.DataFrame(history),hide_index=True,use_container_width=True)
                        continue
                st.dataframe(pd.DataFrame([{
                    "종목":x["name"],"스캔 점수":x["score"],
                    "진입 하단":x["entry_low"],"진입 상단":x["entry_high"],
                    "손절 기준":x["stop"],"1차 목표":x["target"],
                } for x in frozen["candidates"]]),hide_index=True,use_container_width=True)
        st.caption("손절·목표가는 장전 스캐너의 기존 값만 사용합니다. 시세가 없거나 오래되면 WAIT. 보유 수량/평단은 자동 확인하지 않으므로 실제 보유/매도 지시는 아닙니다.")
    panel()
