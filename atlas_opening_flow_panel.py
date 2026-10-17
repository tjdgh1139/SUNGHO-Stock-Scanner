"""Visible opening money-flow diagnostics for the three KIS-subscribed KR stocks.

Not a full-sector scan: only 005930, 000660, 009150 are monitored.
Full-market sector leader claims require wider live coverage and baselines.
"""
from datetime import datetime,timezone
import streamlit as st
from opening_flow_radar import opening_minute,turnover_change,rank_sector_inflows
from atlas_ws_panel import live_state

STOCKS={"005930":"삼성전자","000660":"SK하이닉스","009150":"삼성전기"}
MONITORED={"semiconductor/watchlist":set(STOCKS)}


def render_opening_flow_panel(tape_factory):
    with st.container(border=True):
        st.markdown("### ⚡ 개장 직후 1·3·5분 자금 집중 레이더")
        st.caption("KIS WS 검증된 3종목만 비교 · 전 시장 섹터 순위 아님 · 프로그램 매매 ≠ 외국인 수급")
        if "atlas_opening_prev" not in st.session_state:
            st.session_state.atlas_opening_prev={}
        if "atlas_opening_changes" not in st.session_state:
            st.session_state.atlas_opening_changes={}
        if "atlas_opening_day" not in st.session_state:
            st.session_state.atlas_opening_day=None

        @st.fragment(run_every="2s")
        def panel():
            now=datetime.now(timezone.utc)
            minute=opening_minute(now,"KR")
            day=now.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
            if st.session_state.atlas_opening_day!=day:
                st.session_state.atlas_opening_day=day
                st.session_state.atlas_opening_prev={}
                st.session_state.atlas_opening_changes={}
            if minute is None:
                st.caption("KRX 개장 후 첫 5분이 아니므로 신규 신호는 대기합니다.")
                return
            bucket="1분" if minute<1 else "3분" if minute<3 else "5분"
            rows,connected,_=tape_factory().snapshots()
            updates=[]
            for code,name in STOCKS.items():
                q=rows.get(code,{})
                if live_state(q,connected,now)!="실시간 수신 확인":
                    continue
                current={"symbol":code,"sector":"semiconductor/watchlist",
                         "market":"KR","session_date":day,
                         "received_utc":q.get("trade_received_utc"),
                         "cumulative_turnover":q.get("장중거래대금"),
                         "price":q.get("현재가")}
                previous=st.session_state.atlas_opening_prev.get(code)
                if previous:
                    change=turnover_change(previous,current,now=now)
                    if change:
                        updates.append((previous,current))
                        st.session_state.atlas_opening_changes[code]=change
                # Do not store duplicate WS messages as new intervals.
                if current["received_utc"] and (
                    previous is None or current["received_utc"]!=previous["received_utc"]
                ):
                    st.session_state.atlas_opening_prev[code]=current
            # Display only recent, comparable deltas; never fill missing symbols as zero.
            results=list(st.session_state.atlas_opening_changes.values())
            st.caption(f"개장 후 {minute:.1f}분 · {bucket} 관찰 구간 · WS 정상 변화 {len(results)}/3종목")
            if results:
                for item in sorted(results,key=lambda x:x["rate_per_min"],reverse=True):
                    st.write(f"{STOCKS[item['symbol']]} · 관찰 거래대금 증가속도 {item['rate_per_min']/1e8:.3f}억원/분 · 구간 주가 {item['price_change_pct']:+.2f}%")
            else:
                st.info("최근 체결과 이전 체결의 비교 자료가 아직 부족합니다.")
            st.caption("표시된 거래대금은 매수 순유입이 아닌 체결 거래대금입니다. 섹터 전체 순위·BUY 판정은 제공하지 않습니다.")
        panel()
