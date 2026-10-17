"""ATLAS automatic paper observation panel, session-scoped and read-only.

Records A frozen and B dynamic KR candidates only after a verified live WS
trade. A paper fill requires a *later* trade. It is not an actual transaction.
US quotes currently lack authenticated exchange trade timestamps, so US paper
fills are disabled rather than fabricated.
"""
from datetime import datetime, timezone
import json
import os
import streamlit as st
from atlas_paper_sqlite import load_state,save_events
import pandas as pd
from atlas_paper_live_bridge import empty_ledger,step_ledger,session_report


def render_paper_live_panel(tape_factory):
    st.markdown("### 🧪 ATLAS 자동 가상매매 검증")
    st.caption("스캔 버튼 불필요 · A 장전 고정 / B 실시간 후보 · 검증된 KIS 체결 후 별도 체결로 가상진입 · 실제 주문 없음")
    db_path=os.environ.get("ATLAS_PAPER_DB_PATH","").strip()
    namespace=os.environ.get("ATLAS_PAPER_NAMESPACE","").strip()
    durable_configured=bool(db_path and namespace)
    if "atlas_paper_pending_events" not in st.session_state:
        st.session_state.atlas_paper_pending_events=[]
    if "atlas_paper_live_state" not in st.session_state:
        if durable_configured:
            try:
                st.session_state.atlas_paper_live_state=load_state(db_path,namespace)
                st.session_state.atlas_paper_storage_error=None
            except Exception as exc:
                st.session_state.atlas_paper_live_state=empty_ledger()
                st.session_state.atlas_paper_storage_error=type(exc).__name__
        else:
            st.session_state.atlas_paper_live_state=empty_ledger()
            st.session_state.atlas_paper_storage_error=None

    @st.fragment(run_every="2s")
    def board():
        state=st.session_state.atlas_paper_live_state
        tape=tape_factory()
        ws,connected,error=tape.snapshots()
        now=datetime.now(timezone.utc)
        from zoneinfo import ZoneInfo
        day=now.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
        frozen=st.session_state.get("atlas_frozen_KR",{})
        a=(frozen.get("candidates",[]) if frozen.get("session_date")==day else [])
        b=st.session_state.get("atlas_paper_b_kr_candidates",[])
        state,emitted=step_ledger(
            state,a_candidates=a,b_candidates=b,ws_rows=ws,
            connected=connected,venue=getattr(tape,"market",None),now=now)
        st.session_state.atlas_paper_live_state=state
        if emitted:
            st.session_state.atlas_paper_pending_events.extend(emitted)
        if durable_configured and st.session_state.atlas_paper_pending_events:
            try:
                save_events(db_path,namespace,st.session_state.atlas_paper_pending_events)
                st.session_state.atlas_paper_pending_events=[]
                st.session_state.atlas_paper_storage_error=None
            except (OSError,ValueError,RuntimeError,Exception) as exc:
                st.session_state.atlas_paper_storage_error=type(exc).__name__
        c1,c2,c3=st.columns(3)
        c1.metric("가상 관찰 신호",len(state["signals"]))
        c2.metric("후속 체결 확인",len(state["fills"]))
        c3.metric("수익률 평가 기록",len(state["outcomes"]))
        if not connected:
            st.caption("KIS 실시간 WS 미연결 · 가상 진입 중단 (기존 기록 유지)")
        if error:
            st.caption("수신 상태: "+str(error)[:80])
        rows=[]
        for key,signal in list(state["signals"].items())[-20:]:
            fill=state["fills"].get(key)
            outcome=state["outcomes"].get((key,"5m"))
            rows.append({"시장":"KR","구분":signal["origin"],
                         "종목":signal["symbol"],"신호 시각 UTC":signal["signal_time_utc"],
                         "신호가":signal["signal_price"],
                         "가상진입":round(fill["paper_entry"],2) if fill else None,
                         "5분 순수익%":outcome["net_return_pct"] if outcome else None,
                         "상태":"5분 검증" if outcome else "가상 체결" if fill else "후속 체결 대기"})
        if rows:
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        else:
            st.info("인증된 장중 체결로 후보 신호가 확인되면 여기서 자동 기록합니다.")
        reports=session_report(state)
        st.caption("5분 성적: "+(
            f"{reports['5m']['count']}건 · 평균 순수익 {reports['5m']['avg_net_return_pct']:+.2f}% · 승률 {reports['5m']['win_rate_pct']:.1f}%"
            if reports["5m"]["count"] else "검증된 결과 없음"))
        st.caption("🇺🇸 미국 후보는 인증된 체결 시각과 호가 검증 전까지 가상 진입하지 않습니다.")
        if durable_configured and not st.session_state.atlas_paper_storage_error:
            st.caption("SQLite 자동 저장 활성화 · 서버 영구 볼륨이 연결된 경우에만 재시작 후 보존됩니다.")
        elif durable_configured:
            st.warning("자동 저장 실패 · 세션 임시 기록만 유지 · "+str(st.session_state.atlas_paper_storage_error))
        else:
            st.caption("현재 세션에만 보관 · 영구 저장은 서버의 ATLAS_PAPER_DB_PATH와 ATLAS_PAPER_NAMESPACE 및 영구 볼륨 설정 필요")
        st.caption("브라우저를 닫으면 신규 체결 추적이 중지됩니다. 상시 서버 수집기는 별도 작업입니다.")
        if state["events"]:
            payload="".join(json.dumps(e,ensure_ascii=False,sort_keys=True)+"\n"
                            for e in state["events"])
            st.download_button("가상매매 기록 JSONL 저장",payload,
                               file_name="atlas_paper_session.jsonl",
                               mime="application/x-ndjson",
                               key="atlas_paper_download")
    board()
