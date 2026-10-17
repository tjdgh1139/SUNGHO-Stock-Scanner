"""Render saved, source-verified premarket candidates automatically."""
import streamlit as st
import pandas as pd
from atlas_preopen_feed import read_snapshot

def render_published_preopen():
    with st.container(border=True):
        st.markdown("### NXT 개장 전 자동 TOP 5")
        st.caption("07:00 1차 · 07:55 2차 · NXT 체결은 08:00부터 별도 검증")
        @st.fragment(run_every="15s")
        def panel():
            snapshot=read_snapshot()
            if not snapshot:
                st.warning("오늘 검증된 장전 후보 스냅샷이 없습니다.")
                return
            st.caption("단계: "+snapshot["stage"]+" · 기준 UTC "+snapshot["generated_at_utc"])
            items=snapshot["candidates"]
            if not items:
                st.info("확인된 후보 없음")
                return
            st.dataframe(pd.DataFrame([{
                "순위":i,"종목":c["name"],"섹터":c.get("sector",""),
                "점수":c["score"],"근거":c.get("reason",""),
            } for i,c in enumerate(items,1)]),hide_index=True,use_container_width=True)
            st.caption("장전 예측 후보 · 실시간 NXT 체결이나 확정 BUY 신호가 아닙니다.")
        panel()
