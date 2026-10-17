"""Two separate automatic KR and US early-momentum candidate panels.

On-page 30s refresh. The KR feed rotates 6 KIS REST symbols per batch
through a bounded KRX universe; US is the first KIS movers page per exchange.
No background 24/7 service and no actual trade execution.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import time
import pandas as pd
import streamlit as st
from atlas_auto_candidates import (
    KR_BATCH,KR_INTERVAL,US_INTERVAL,KR_UNIVERSE_LIMIT,
    kr_regular_hours,us_regular_hours,normalized_kr_universe,
    kr_candidate,us_candidates,fresh_ranked,
)


def render_auto_candidate_board(listing_fn,kis_quote_fn,kis_us_movers_fn,kis_configured_fn):
    st.markdown("### 🚀 ATLAS 자동 급등 후보 탐색")
    st.caption("스캔 버튼 불필요 · 한국 KRX 순환 조회 / 미국 Nasdaq·NYSE·NYSE American 급등 순위 · 화면이 열려 있을 때만 동작")
    if not kis_configured_fn():
        st.warning("KIS API 연결이 필요합니다. 검증되지 않은 후보는 표시하지 않습니다.")
        return

    if "atlas_auto_kr_universe" not in st.session_state:
        st.session_state.atlas_auto_kr_universe=[]
    if "atlas_auto_kr_cursor" not in st.session_state:
        st.session_state.atlas_auto_kr_cursor=0
    if "atlas_auto_kr_seen" not in st.session_state:
        st.session_state.atlas_auto_kr_seen={}
    if "atlas_auto_kr_scanned" not in st.session_state:
        st.session_state.atlas_auto_kr_scanned=set()
    if "atlas_auto_kr_last" not in st.session_state:
        st.session_state.atlas_auto_kr_last=-1e12
    if "atlas_auto_us_last" not in st.session_state:
        st.session_state.atlas_auto_us_last=-1e12
    if "atlas_auto_us_rows" not in st.session_state:
        st.session_state.atlas_auto_us_rows=[]
    if "atlas_auto_us_diag" not in st.session_state:
        st.session_state.atlas_auto_us_diag={}

    @st.fragment(run_every="30s")
    def board():
        now=datetime.now(timezone.utc)
        mono=time.monotonic()
        kr_open=kr_regular_hours(now)
        us_open=us_regular_hours(now)
        if kr_open and mono-st.session_state.atlas_auto_kr_last>=KR_INTERVAL:
            st.session_state.atlas_auto_kr_last=mono
            if not st.session_state.atlas_auto_kr_universe:
                try:
                    st.session_state.atlas_auto_kr_universe=normalized_kr_universe(listing_fn())
                except Exception:
                    st.session_state.atlas_auto_kr_universe=[]
            universe=st.session_state.atlas_auto_kr_universe
            if universe:
                cursor=st.session_state.atlas_auto_kr_cursor
                for i in range(min(KR_BATCH,len(universe))):
                    code,name=universe[(cursor+i)%len(universe)]
                    st.session_state.atlas_auto_kr_scanned.add(code)
                    try:
                        q=kis_quote_fn(code,market="J")
                        if q:
                            item=kr_candidate(code,name,q,now=datetime.now(timezone.utc))
                            if item:
                                st.session_state.atlas_auto_kr_seen[code]=item
                    except Exception:
                        continue
                st.session_state.atlas_auto_kr_cursor=(cursor+KR_BATCH)%len(universe)
        if us_open and mono-st.session_state.atlas_auto_us_last>=US_INTERVAL:
            st.session_state.atlas_auto_us_last=mono
            try:
                frame,diag=kis_us_movers_fn(1_000_000)
                st.session_state.atlas_auto_us_rows=us_candidates(frame,datetime.now(timezone.utc))
                st.session_state.atlas_auto_us_diag=diag
            except Exception as exc:
                st.session_state.atlas_auto_us_rows=[]
                st.session_state.atlas_auto_us_diag={"error":type(exc).__name__}
        kr=fresh_ranked(list(st.session_state.atlas_auto_kr_seen.values()),datetime.now(timezone.utc))
        us=fresh_ranked(st.session_state.atlas_auto_us_rows,datetime.now(timezone.utc))
        left,right=st.columns(2,gap="medium")
        with left:
            st.markdown("#### 🇰🇷 한국 급등 유력 *관찰* 후보")
            covered=st.session_state.atlas_auto_kr_universe
            cursor=st.session_state.atlas_auto_kr_cursor
            st.caption(f"KRX {'장중' if kr_open else '장외'} · 순환 범위 {len(covered):,}종목 · 순환 조회 시도 {len(st.session_state.atlas_auto_kr_scanned):,}개 · 회당 {KR_BATCH}종목")
            if kr:
                st.dataframe(pd.DataFrame([{
                    "종목":x["종목"],"가격(원)":int(x["현재가"]),
                    "등락%":x["등락%"],"거래대금(억)":round(x["거래대금"]/1e8,1),
                    "관찰점수":x["점수"],"판정":"WATCH",
                } for x in kr]),hide_index=True,use_container_width=True)
            else:
                st.info("현재 조건·수신시각을 통과한 한국 후보 없음")
        with right:
            st.markdown("#### 🇺🇸 미국 급등 유력 *관찰* 후보")
            st.caption("미국 정규장 "+("운영" if us_open else "시간 외")+
                       " · 3개 거래소 급등 순위 첫 페이지 · 전체 종목 전수 검색 아님")
            if us:
                st.dataframe(pd.DataFrame([{
                    "종목":x["코드"],"가격($)":x["현재가"],
                    "등락%":x["등락%"],"최근5분%":x["최근5분%"],
                    "거래대금($)":int(x["거래대금"]),
                    "관찰점수":x["점수"],"판정":"WATCH",
                } for x in us]),hide_index=True,use_container_width=True)
            else:
                st.info("현재 조건·수신시각을 통과한 미국 후보 없음")
        st.caption("수익을 보장하는 BUY 신호가 아닙니다. "
                   "REST 수신시각은 체결시각이 아니며 외국인·기관 수급 및 상대 거래량 검증은 별도입니다. "
                   "시장 휴장일은 추가 확인 필요. 페이지를 닫으면 자동 스캔이 중지됩니다.")
    board()
