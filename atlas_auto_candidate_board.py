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
from atlas_ws_panel import live_state
from atlas_nxt_revalidation import market_phase,nxt_fresh_quote
from atlas_prebreakout import rank_prebreakout_kr,rank_prebreakout_us,turnover_momentum
from atlas_kis_readonly import WATCHLIST
from atlas_auto_candidates import (
    KR_BATCH,KR_INTERVAL,US_INTERVAL,KR_UNIVERSE_LIMIT,
    kr_regular_hours,us_regular_hours,normalized_kr_universe,
    kr_candidate,us_candidates,fresh_ranked,live_ws_to_kr_quote,
)


def render_auto_candidate_board(listing_fn,kis_quote_fn,kis_us_movers_fn,kis_configured_fn,
                                tape_factory,websocket_capability,secret_value):
    st.markdown("### 🎯 ATLAS 급등 *전* 유력 후보")
    st.caption("스캔 버튼 불필요 · NXT 08:00부터 인증된 WS 후보 반영 · 화면 2초 갱신 / KRX REST 30초 순환 / 미국 순위 60초 조회 · 페이지 열려 있을 때만")
    if not kis_configured_fn():
        st.warning("KIS API 연결이 필요합니다. 검증되지 않은 후보는 표시하지 않습니다.")
        return

    if "atlas_auto_kr_universe" not in st.session_state:
        st.session_state.atlas_auto_kr_universe=[]
    if "atlas_auto_kr_cursor" not in st.session_state:
        st.session_state.atlas_auto_kr_cursor=0
    if "atlas_auto_kr_seen" not in st.session_state:
        st.session_state.atlas_auto_kr_seen={}
    if "atlas_auto_kr_history" not in st.session_state:
        st.session_state.atlas_auto_kr_history={}
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

    def record_kr_item(code,item,quote,source):
        key=(source,code)
        old=st.session_state.atlas_auto_kr_history.get(key)
        if old:
            rate,acc=turnover_momentum(old["quote"],quote,old.get("rate"))
            if acc is not None and 0<=acc<=100:
                item["turnover_acceleration"]=acc
        else:
            rate=None
        st.session_state.atlas_auto_kr_history[key]={"quote":dict(quote),"rate":rate}
        st.session_state.atlas_auto_kr_seen[code]=item

    @st.fragment(run_every="2s")
    def board():
        now=datetime.now(timezone.utc)
        mono=time.monotonic()
        kr_open=kr_regular_hours(now)
        nxt_open=market_phase(now)=="NXT_PRE"
        kr_active=kr_open or nxt_open
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
                core=[pair for pair in WATCHLIST if pair[0] in {c for c,_ in universe}]
                slots=max(0,KR_BATCH-len(core))
                batch=core+[universe[(cursor+i)%len(universe)] for i in range(min(slots,len(universe)))]
                batch=list(dict((c,(c,n)) for c,n in batch).values())
                for code,name in batch:
                    st.session_state.atlas_auto_kr_scanned.add(code)
                    try:
                        q=kis_quote_fn(code,market="J")
                        if q:
                            item=kr_candidate(code,name,q,now=datetime.now(timezone.utc))
                            if item:
                                record_kr_item(code,item,q,"REST")
                    except Exception:
                        continue
                st.session_state.atlas_auto_kr_cursor=(cursor+slots)%len(universe)
        if us_open and mono-st.session_state.atlas_auto_us_last>=US_INTERVAL:
            st.session_state.atlas_auto_us_last=mono
            try:
                frame,diag=kis_us_movers_fn(1_000_000)
                st.session_state.atlas_auto_us_rows=us_candidates(frame,datetime.now(timezone.utc))
                st.session_state.atlas_auto_us_diag=diag
            except Exception as exc:
                st.session_state.atlas_auto_us_rows=[]
                st.session_state.atlas_auto_us_diag={"error":type(exc).__name__}
        # One existing KIS WebSocket session: auto-connect the 3 core stocks
        # without requiring a separate Scan button; no extra socket is created.
        tape=tape_factory()
        if kr_open and websocket_capability() and (
            mono-st.session_state.get("atlas_auto_ws_attempt",-1e12)>=120
        ):
            st.session_state.atlas_auto_ws_attempt=mono
            if getattr(tape,"market",None) in (None,"J") and not (
                getattr(tape,"thread",None) and tape.thread.is_alive()
            ):
                try:
                    tape.start(tuple(code for code,_ in WATCHLIST),
                               secret_value("KIS_APP_KEY"),secret_value("KIS_APP_SECRET"),market="J")
                except Exception:
                    pass
        ws_rows,ws_connected,_=tape.snapshots()
        for code,name in WATCHLIST:
            live=ws_rows.get(code,{})
            if live_state(live,ws_connected)=="실시간 수신 확인":
                live_quote=live_ws_to_kr_quote(live)
                item=kr_candidate(code,name,live_quote,datetime.now(timezone.utc)) if live_quote else None
                if item:
                    item["source"]="KIS WS · 체결/호가/프로그램 최근 10초 확인"
                    record_kr_item(code,item,live_quote,"WS")
        if nxt_open and getattr(tape,"market",None)=="NX" and ws_connected:
            for code,live in ws_rows.items():
                verified=nxt_fresh_quote(live,now=datetime.now(timezone.utc))
                if not verified:
                    continue
                symbol=str(code)
                name=next((n for c,n in st.session_state.atlas_auto_kr_universe if c==symbol),symbol)
                nxt_quote={"현재가":verified["price"],
                           "장중등락%":live.get("등락%"),
                           "장중거래대금":verified["turnover"],
                           "장중거래량":verified["volume"],
                           "quote_received_utc":verified["received_utc"],
                           "장중고가":live.get("장중고가"),
                           "체결강도":verified["strength"],
                           "프로그램순매수대금":live.get("프로그램순매수대금")}
                item=kr_candidate(symbol,name,nxt_quote,now=datetime.now(timezone.utc),min_turnover=200_000_000)
                if item:
                    item["source"]="KIS WS NXT · authenticated venue, no investor inference"
                    record_kr_item(symbol,item,nxt_quote,"NXT")
        kr=fresh_ranked(list(st.session_state.atlas_auto_kr_seen.values()),datetime.now(timezone.utc))
        us=fresh_ranked(st.session_state.atlas_auto_us_rows,datetime.now(timezone.utc))
        # Early prebreakout WATCH shortlist, not today's top gainers.
        pre_kr=rank_prebreakout_kr(list(st.session_state.atlas_auto_kr_seen.values()),
                                   now=datetime.now(timezone.utc),limit=3,
                                   min_turnover=200_000_000 if nxt_open else 3_000_000_000) if kr_active else []
        pre_us=rank_prebreakout_us(st.session_state.atlas_auto_us_rows,
                                   now=datetime.now(timezone.utc),limit=3) if us_open else []
        with st.container(border=True):
            st.markdown("#### 🎯 급등 전조 예측 후보 TOP 3 · 한국 / 미국")
            st.caption("현재 상승률 순위가 아닌 초기 상승·유동성·호가·거래대금 신호 선별 · 예측 정확도 미검증")
            col_kr,col_us=st.columns(2,gap="medium")
            with col_kr:
                st.markdown("**🇰🇷 한국 · 상승 전조 3종목**")
                if pre_kr:
                    for idx,x in enumerate(pre_kr,1):
                        st.markdown(f"**{idx}. {x['종목']}** · {x['현재가']:,.0f}원 · {x['등락%']:+.2f}%")
                        st.caption(f"전조점수 {x['예비점수']:.0f} · {x['근거']} · WATCH")
                else:
                    st.caption("검증 가능한 초기 상승 후보 없음")
            with col_us:
                st.markdown("**🇺🇸 미국 · 상승 전조 3종목**")
                if pre_us:
                    for idx,x in enumerate(pre_us,1):
                        st.markdown(f"**{idx}. {x['코드']}** · ${x['현재가']:,.2f} · {x['등락%']:+.2f}%")
                        st.caption(f"전조점수 {x['예비점수']:.0f} · 최근5분 {x['최근5분%']:+.2f}% · WATCH")
                else:
                    st.caption("검증 가능한 초기 상승 후보 없음")
            st.caption("최대 3종목씩, 조건 미달 시 빈칸. 국내 순환 조회·미국 순위 첫 페이지에 한정됩니다.")
        st.divider()
        # Separate dynamically reranked TOP5 from the frozen pre-open watchlist.
        kr=rank_prebreakout_kr(kr,now=datetime.now(timezone.utc),limit=5,
                               min_turnover=200_000_000 if nxt_open else 3_000_000_000) if kr_active else []
        us=rank_prebreakout_us(us,now=datetime.now(timezone.utc),limit=5) if us_open else []
        # Expose the exact ranked candidates to the paper-only observer.
        # No buy order or fabricated fill is generated here.
        st.session_state["atlas_paper_b_kr_candidates"]=[
            dict(x, symbol=x["코드"]) for x in kr
        ]
        st.session_state["atlas_paper_b_us_candidates"]=[
            dict(x, symbol=x["코드"]) for x in us
        ]
        left,right=st.columns(2,gap="medium")
        with left:
            st.markdown("#### 🇰🇷 B. 한국 신규 전조 후보 TOP 5")
            covered=st.session_state.atlas_auto_kr_universe
            cursor=st.session_state.atlas_auto_kr_cursor
            st.caption(f"{'NXT 프리마켓' if nxt_open else 'KRX 장중' if kr_open else '장외'} · 순환 범위 {len(covered):,}종목 · 순환 조회 시도 {len(st.session_state.atlas_auto_kr_scanned):,}개 · 회당 {KR_BATCH}종목")
            if kr:
                st.dataframe(pd.DataFrame([{
                    "종목":x["종목"],"가격(원)":int(x["현재가"]),
                    "등락%":x["등락%"],"거래대금(억)":round(x["거래대금"]/1e8,1),
                    "전조점수":x["예비점수"],"판정":"WATCH",
                } for x in kr]),hide_index=True,use_container_width=True)
            else:
                st.info("현재 검증 가능한 한국 상승 전조 후보 없음")
        with right:
            st.markdown("#### 🇺🇸 B. 미국 신규 전조 후보 TOP 5")
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
                st.info("현재 검증 가능한 미국 상승 전조 후보 없음")
        st.caption("B 후보는 2초마다 재평가되고 오래된 후보는 자동 제외됩니다. 검증된 전 시장 실시간 순위가 아닙니다. "
                   "수익을 보장하는 BUY 신호가 아닙니다. "
                   "REST 수신시각은 체결시각이 아니며 외국인·기관 수급 및 상대 거래량 검증은 별도입니다. "
                   "시장 휴장일은 추가 확인 필요. 페이지를 닫으면 자동 스캔이 중지됩니다.")
    board()
