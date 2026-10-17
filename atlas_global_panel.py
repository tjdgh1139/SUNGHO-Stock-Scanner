"""Read-only macro sidebar: source-stamped PUBLIC delayed quotes, never live claims."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from market_indicators import INDICATORS, get_indicator
from treasury_yields import treasury_yields

CORE = (
    "미국 변동성 VIX", "달러지수 DXY", "필라델피아 반도체 SOX",
    "반도체 3배 ETF SOXL", "미국 러셀2000", "달러/원 USDKRW",
    "브렌트유 선물",
)


@st.cache_data(ttl=90, show_spinner=False)
def _read_indicators(names):
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(get_indicator, name):name for name in names}
        for task in as_completed(tasks):
            name=tasks[task]
            try:
                rows.append(task.result())
            except Exception:
                rows.append({"지표":name,"상태":"미수신 · 조회 실패"})
    return sorted(rows,key=lambda r:names.index(r["지표"]))


@st.cache_data(ttl=1800,show_spinner=False)
def _read_treasury():
    return treasury_yields()


def render_global_indices():
    with st.expander("🌍 ATLAS 중요 지수·변동성·반도체", expanded=False):
        st.caption("공개 지연시세 · 거래소 실시간 인증 아님 · 수신시각과 시세 기준시각 구분")
        expanded = st.checkbox("아시아·금·구리 지표도 표시",value=False,key="atlas_global_full")
        auto = st.toggle("90초마다 자동 조회 (화면 열려 있을 때)",value=False,key="atlas_global_auto")
        names=tuple(INDICATORS) if expanded else CORE

        @st.fragment(run_every="90s" if auto else None)
        def panel():
            clicked = st.button("🔄 중요 지수 조회",key="atlas_global_refresh")
            if clicked:
                _read_indicators.clear()
                _read_treasury.clear()
            if not st.session_state.get("atlas_global_loaded") and not auto:
                st.caption("조회 버튼을 누르면 최신 확인 가능한 지연 시세를 표시합니다.")
                if not clicked:
                    return
            st.session_state.atlas_global_loaded=True
            rows=_read_indicators(names)
            out=[]
            for r in rows:
                stamp=r.get("기준일")
                kst=pt="—"
                if stamp:
                    try:
                        dt=datetime.fromisoformat(stamp.replace("Z","+00:00"))
                        kst=dt.astimezone(ZoneInfo("Asia/Seoul")).strftime("%m-%d %H:%M")
                        pt=dt.astimezone(ZoneInfo("America/Los_Angeles")).strftime("%m-%d %H:%M")
                    except ValueError:
                        pass
                val=r.get("최근값")
                out.append({"지표":r["지표"],
                            "값":f"{val:,.2f}" if isinstance(val,(int,float)) else "미수신",
                            "등락%":r.get("전일대비%"),
                            "기준 KST":kst,"기준 PT":pt,
                            "상태":r.get("상태","미확인")})
            st.dataframe(pd.DataFrame(out),hide_index=True,use_container_width=True)
            st.caption("SOX는 반도체 지수, SOXL은 일일 3배 레버리지 ETF입니다. 서로 대체하지 않습니다.")
            st.caption("미국 국채 2·10·30년 수익률: FRED 공식 일별 자료(실시간 아님)")
            st.dataframe(pd.DataFrame(_read_treasury()),hide_index=True,use_container_width=True)
        panel()
