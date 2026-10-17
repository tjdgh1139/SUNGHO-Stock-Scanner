"""ATLAS foreign/institution accumulation shortlist from verified KIS EOD data."""
import time
import streamlit as st
import pandas as pd
from atlas_kis_readonly import WATCHLIST, token_request
from foreign_flow import investor_history,confirmed_flow
from atlas_ws_panel import live_state


@st.cache_data(ttl=3300,show_spinner=False)
def _token(key,secret):
    return token_request(key,secret)


def candidate_codes(scan,limit=10):
    codes=[(code,name) for code,name in WATCHLIST]
    if isinstance(scan,pd.DataFrame) and not scan.empty and "코드" in scan.columns:
        frame=scan.sort_values("점수",ascending=False) if "점수" in scan.columns else scan
        for _,row in frame.iterrows():
            code=str(row["코드"]).zfill(6)
            if len(code)==6 and code.isdigit() and code not in [x[0] for x in codes]:
                codes.append((code,str(row.get("종목",code))))
            if len(codes)>=limit:
                break
    return codes[:limit]


def rank_flow(results,ws_rows=None,connected=False,now=None):
    ws_rows=ws_rows or {}
    out=[]
    for item in results:
        if not item or not item.get("confirmed"):
            continue
        code=item["code"]
        live=ws_rows.get(code,{})
        ws_verified=live_state(live,connected,now)=="실시간 수신 확인"
        strength=float(live.get("체결강도") or 0) if ws_verified else 0
        prog=float(live.get("프로그램순매수대금") or 0) if ws_verified else 0
        change=float(live.get("등락%") or 0) if ws_verified else 0
        # EOD accumulation + live program are DIFFERENT data sources.
        candidate=(item["signal"]=="FLOW_WATCH" and ws_verified
                   and strength>=110 and prog>0 and change>0)
        out.append({**item,"live_verified":ws_verified,
                    "stage":"진입 검토" if candidate else "관찰/대기",
                    "trade_strength":strength if ws_verified else None,
                    "program_net":prog if ws_verified else None})
    return sorted(out,key=lambda x:(x["stage"]=="진입 검토",x["score"],x["foreign_3d"]),reverse=True)


def render_foreign_flow_panel(scan,tape_factory,secret_value):
    with st.expander("🔥 외국인·기관 수급 급증 후보",expanded=True):
        st.caption("KIS 공식 투자자별 확정 수급(전일 이전) + 장중 프로그램/체결강도 교차 검증 · 자동 주문 없음")
        names=candidate_codes(scan,limit=10)
        st.caption("조회 대상: "+", ".join(name for _,name in names))
        if st.button("🔍 실제 외국인·기관 순매수 후보 스캔",key="atlas_foreign_scan",type="primary"):
            try:
                key=secret_value("KIS_APP_KEY")
                secret=secret_value("KIS_APP_SECRET")
                token=_token(key,secret)
                results=[]
                for i,(code,name) in enumerate(names):
                    if i:time.sleep(0.35)
                    raw=investor_history(code,key,secret,token)
                    flow=confirmed_flow(code,raw)
                    if flow:
                        results.append({**flow,"name":name})
                st.session_state.atlas_foreign_results=results
            except (KeyError,ValueError,TypeError) as exc:
                st.warning("KIS 투자자 수급 조회 준비 실패: "+type(exc).__name__)
        results=st.session_state.get("atlas_foreign_results",[])
        if not results:
            st.info("조회 버튼을 누르면 확인된 외국인·기관 순매수 후보를 보여줍니다.")
            return
        rows,connected,_=tape_factory().snapshots()
        ranked=rank_flow(results,rows,connected)
        if not ranked:
            st.warning("확정 수급 데이터 부족 · 종목을 매수 후보로 표시하지 않습니다.")
            return
        st.dataframe(pd.DataFrame([{
            "종목":r.get("name",r["code"]),
            "확정일":r["latest_date"],
            "외국인 1일 순매수(주)":r["foreign_1d"],
            "외국인 3일 누적(주)":r["foreign_3d"],
            "기관 3일 누적(주)":r["institution_3d"],
            "수급 점수":r["score"],
            "실시간 수급 교차": "확인" if r["live_verified"] else "미확인",
            "판정":r["stage"],
        } for r in ranked]),hide_index=True,use_container_width=True)
        st.caption("⚠️ 외국인·기관 수급은 장중 실시간 확정치가 아닙니다. "
                   "프로그램 매매를 외국인 수급으로 표시하지 않습니다. "
                   "진입 검토도 매수 보장 신호가 아니며 실제 수익률 검증이 필요합니다.")
