
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import csv
from datetime import datetime, timezone
import requests
import json
import time
import threading
import hashlib
import uuid
import html
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from feeds import dart_corporations, naver_news, FeedError
from ws_protocol import parse_market_packet
from scoring import overlay_quote, decorate_chart
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import FinanceDataReader as fdr
except Exception:
    fdr = None


AUDIT_DIR = Path("scanner_audit") / st.session_state.setdefault("audit_owner",str(uuid.uuid4()))
AUDIT_DIR.mkdir(parents=True,exist_ok=True)
AUDIT_FILE = AUDIT_DIR / "scan_snapshots.csv"

def candle_chart(history, title="", minute=False, currency="KRW"):
    """Render real OHLC candles with aligned volume; keep early indicator NaNs."""
    h=history.copy().sort_index()
    required=["시가","고가","저가","종가"]
    if not all(c in h for c in required):
        raise ValueError("캔들에 필요한 시가·고가·저가·종가 데이터가 없습니다.")
    h[required]=h[required].apply(pd.to_numeric,errors="coerce")
    h=h.dropna(subset=required)
    if h.empty:raise ValueError("유효한 캔들 데이터가 없습니다.")
    x=h.index.strftime("%m-%d %H:%M" if minute else "%Y-%m-%d")
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,
                      row_heights=[.78,.22],vertical_spacing=.035)
    fig.add_trace(go.Candlestick(x=x,open=h["시가"],high=h["고가"],low=h["저가"],close=h["종가"],
        name="캔들",increasing_line_color="#e53935",increasing_fillcolor="#e53935",
        decreasing_line_color="#1976d2",decreasing_fillcolor="#1976d2"),row=1,col=1)
    for column,name,color in [("MA5","5일선","#8e44ad"),("MA20","20일선","#ff9800"),
                               ("MA60","60일선","#4caf50"),("BB_UPPER","BB 상단","#90a4ae"),
                               ("BB_LOWER","BB 하단","#90a4ae")]:
        if column in h:
            fig.add_trace(go.Scatter(x=x,y=h[column],name=name.replace("일선","분선") if minute else name,
                mode="lines",line=dict(color=color,width=2.5 if column=="MA20" else 1),
                connectgaps=False),row=1,col=1)
    if "거래량" in h:
        fig.add_trace(go.Bar(x=x,y=h["거래량"],name="거래량",showlegend=False,
            marker_color=np.where(h["종가"]>=h["시가"],"#e53935","#1976d2")),row=2,col=1)
    fig.update_layout(title=title,height=590,margin=dict(l=8,r=8,t=50,b=30),
        legend=dict(orientation="h",y=1.08,x=0),hovermode="x unified",
        xaxis_rangeslider_visible=False,dragmode="pan")
    fig.update_xaxes(type="category",nticks=7,rangeslider_visible=False)
    if currency not in ("KRW","USD"):raise ValueError("unsupported currency")
    fig.update_yaxes(title_text="가격 (원)" if currency=="KRW" else "가격 (USD)",
                     tickformat=",.0f" if currency=="KRW" else ",.2f",
                     tickprefix="" if currency=="KRW" else "$",ticksuffix="원" if currency=="KRW" else "",
                     fixedrange=False,row=1,col=1)
    fig.update_yaxes(title_text="거래량",rangemode="tozero",row=2,col=1)
    return fig

def change_color(value):
    number=_safe_num(value)
    return "#e53935" if number>0 else "#1976d2" if number<0 else "#757575"

def colored_quote(label,value,change):
    color=change_color(change)
    st.markdown(f'<div style="border:1px solid #ddd;border-radius:12px;padding:10px"><span style="font-size:16px;font-weight:700">{html.escape(str(label))}</span><br><span style="font-size:2rem;font-weight:700;color:{color}">{html.escape(str(value))}</span><br><span style="font-size:16px;font-weight:600;color:{color}">{_safe_num(change):+.2f}%</span></div>',unsafe_allow_html=True)

def candidate_formats(frame,currency="KRW"):
    formats={}
    for c in frame.columns:
        if c in ("현재가","종가","매수하단","매수상단","돌파확인가","손절가","1차목표","2차목표","진입검토목표","평단","익절가","평가손익"):
            formats[c]="%,.0f원" if currency=="KRW" else "$%,.2f"
        elif "%" in c or c=="등락률":formats[c]="%+.2f%%"
        elif "손익비" in c:formats[c]="%.2f"
        elif "점수" in c or c in ("거래량x","RSI"):formats[c]="%.1f"
    return formats

def styled_candidate_table(frame,currency="KRW"):
    # One format call: later Styler.format calls otherwise reset earlier columns.
    formats={c:("{:,.0f}원" if currency=="KRW" else "${:,.2f}") for c in frame.columns
             if c in ("현재가","종가","매수하단","매수상단","돌파확인가","손절가","1차목표","2차목표","진입검토목표","평단","익절가","평가손익")}
    formats.update({c:"{:+.2f}%" for c in frame.columns if "%" in c or c=="등락률"})
    formats.update({c:"{:.1f}" for c in frame.columns if "점수" in c or c in ("거래량x","RSI")})
    formats.update({c:"{:.2f}" for c in frame.columns if "손익비" in c})
    style=frame.style.format(formats,na_rep="—")
    if "등락%" in frame:style=style.map(lambda v:"color: "+change_color(v),subset=["등락%"])
    return style

def show_candidate_table(frame,currency="KRW"):
    config={c:st.column_config.NumberColumn(c,format=fmt) for c,fmt in candidate_formats(frame,currency).items()}
    st.dataframe(styled_candidate_table(frame,currency),column_config=config,hide_index=True,use_container_width=True)

def _safe_num(v, default=0.0):
    try:
        x=float(v)
        return default if np.isnan(x) or np.isinf(x) else x
    except Exception:
        return default

def candidate_cards(frame):
    """Compact, escaped summary cards; preserve ranking and source status."""
    cards=[]
    for rank,(_,row) in enumerate(frame.head(5).iterrows(),1):
        name=html.escape(str(row.get("종목","-")))
        code=html.escape(str(row.get("코드","-")))
        status=html.escape(str(row.get("상태","판단보류")))
        confidence=html.escape(str(row.get("데이터신뢰도","일봉/지연")))
        reason=html.escape(str(row.get("진입제한사유","")))
        price=_safe_num(row.get("현재가",row.get("종가",0)))
        change=_safe_num(row.get("등락%",0))
        score=_safe_num(row.get("실시간단타점수",row.get("단타점수",row.get("점수",0))))
        tone="up" if change>0 else "down" if change<0 else "flat"
        cards.append(f'<article class="candidate-card"><div class="card-rank">TOP {rank} · {code}</div>'
                     f'<div class="card-name">{name}</div><div class="card-price">{price:,.0f}<span> 원</span></div>'
                     f'<div class="card-change {tone}">{change:+.2f}%</div>'
                     f'<div class="card-score">단타 점수 <strong>{score:.1f}</strong><span> / 100</span></div>'
                     f'<div class="card-status">{status}</div><div class="card-source">{confidence}</div><div class="card-reason">{reason}</div></article>')
    return '<div class="candidate-grid">'+''.join(cards)+'</div>'

def strategy_scores(row):
    base=_safe_num(row.get("점수",row.get("score",0)))
    rsi=_safe_num(row.get("RSI",50),50)
    osc=_safe_num(row.get("MACD_OSC",row.get("MACD OSC",0)))
    sep=_safe_num(row.get("20일이격",row.get("이격도20",100)),100)
    value=_safe_num(row.get("거래대금",0))
    vr=_safe_num(row.get("거래량비",row.get("거래량배수",1)),1)
    f=_safe_num(row.get("외국인",row.get("외국인순매수",0))) if row.get("수급기준일") else 0
    i=_safe_num(row.get("기관",row.get("기관순매수",0))) if row.get("수급기준일") else 0
    p=_safe_num(row.get("프로그램",row.get("프로그램순매수",0))) if timestamp_fresh(row.get("program_received_utc")) else 0
    ch=_safe_num(row.get("등락률",row.get("등락%",row.get("change_pct",0))))
    flow=sum(1 if x>0 else -1 if x<0 else 0 for x in (f,i,p))
    liq=min(18,np.log10(max(value,1))*2.2) if value>0 else 0
    accel=min(14,max(0,(vr-1)*5))
    chase=-12 if ch>=18 or sep>=120 else (-6 if ch>=10 or sep>=112 else 0)
    day=base*.48+liq+accel+flow*4+(8 if osc>0 else -5)+(7 if 52<=rsi<=72 else -10 if rsi>=82 else 1)+chase
    swing=base*.58+flow*5+(8 if osc>0 else -4)+(6 if 98<=sep<=110 else -5 if sep>=118 else 0)+min(8,liq/2)
    long=base*.62+flow*2+(6 if 45<=rsi<=68 else 0)+(6 if 95<=sep<=108 else -4 if sep>=120 else 0)
    return {"단타점수":round(float(np.clip(day,0,100)),1),"스윙점수":round(float(np.clip(swing,0,100)),1),"장기점수":round(float(np.clip(long,0,100)),1)}

def actionable_levels(row):
    px=_safe_num(row.get("현재가",row.get("종가",row.get("Close",0))))
    atr=_safe_num(row.get("ATR",0)); ma20=_safe_num(row.get("MA20",row.get("20일선",0)))
    if px<=0:return {k:np.nan for k in ("매수관심하단","매수관심상단","돌파확인가","손절기준","1차익절","2차익절","1차손익비")}
    if atr<=0:atr=px*.025
    support=max(0,min(px,ma20) if ma20>0 and ma20<px*1.03 else px-atr*.8)
    lo=max(support,px-atr*.35); hi=px+atr*.15; br=px+atr*.45
    stop=max(px*.01,min(lo-atr*.55,px-atr*.9)); risk=max(hi-stop,px*.008)
    digits=2 if row.get("currency")=="USD" else 0
    return {"매수관심하단":round(lo,digits),"매수관심상단":round(hi,digits),"돌파확인가":round(br,digits),"손절기준":round(stop,digits),
            "1차익절":round(hi+risk*1.8,digits),"2차익절":round(hi+risk*3.0,digits),"1차손익비":1.8}

def signal_state(row):
    d=strategy_scores(row)["단타점수"]; ch=_safe_num(row.get("등락률",row.get("등락%",0)))
    return "추격금지" if ch>=20 else "진입확인" if d>=82 else "관심" if d>=72 else "대기" if d>=60 else "제외"

def data_confidence(row):
    if row.get("currency")=="USD":return "DAILY/DELAYED"
    ts=pd.to_datetime(row.get("quote_received_utc"),utc=True,errors="coerce")
    if pd.isna(ts) or not 0 <= (pd.Timestamp.now(tz="UTC")-ts).total_seconds() <= 120:
        return "DAILY/DELAYED"
    return "LIVE-MED" if _safe_num(row.get("현재가"))>0 else "DAILY/DELAYED"

def enrich_scan_dataframe(df):
    if df is None or len(df)==0:return df
    out=df.copy(); rows=[]
    for _,r in out.iterrows():
        d=r.to_dict(); z={}; z.update(strategy_scores(d)); z.update(actionable_levels(d));z.update(entry_quality(d))
        z["상태"]=execution_permission(d,row_live_health(d)); z["진입위험사유"]=entry_risk_reason(d)
        z["데이터신뢰도"]=data_confidence(d); rows.append(z)
    a=pd.DataFrame(rows,index=out.index)
    for c in a.columns:out[c]=a[c]
    return out

def save_scan_snapshot(df,scan_type="market"):
    if df is None or len(df)==0:return
    e=enrich_scan_dataframe(df); now=datetime.now(timezone.utc).isoformat(); rows=[]
    for rank,(_,r) in enumerate(e.head(50).iterrows(),1):
        d=r.to_dict(); rows.append({"scan_time_utc":now,"scan_type":scan_type,"rank":rank,
          "code":d.get("코드",d.get("Code","")),"name":d.get("종목",d.get("종목명",d.get("Name",""))),
          "price":_safe_num(d.get("현재가",d.get("종가",0))),"day_score":_safe_num(d.get("단타점수",0)),
          "swing_score":_safe_num(d.get("스윙점수",0)),"long_score":_safe_num(d.get("장기점수",0)),
          "stop":_safe_num(d.get("손절기준",0)),"tp1":_safe_num(d.get("1차익절",0)),"tp2":_safe_num(d.get("2차익절",0)),
          "confidence":d.get("데이터신뢰도","")})
    exists=AUDIT_FILE.exists()
    with AUDIT_FILE.open("a",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
        if not exists:w.writeheader()
        w.writerows(rows)

def audit_summary(history_df):
    if history_df is None or len(history_df)==0:return pd.DataFrame()
    m={}
    for h in ("d1_ret","d3_ret","d5_ret"):
        if h in history_df.columns:
            s=pd.to_numeric(history_df[h],errors="coerce").dropna()
            if len(s):m[h]={"count":len(s),"avg_pct":round(s.mean(),2),"median_pct":round(s.median(),2),"win_rate_pct":round((s>0).mean()*100,1)}
    return pd.DataFrame(m).T if m else pd.DataFrame()


# ============================================================
# RISK / REGIME / PORTFOLIO SAFETY LAYER
# ============================================================

def market_regime(index_change_pct=0.0, breadth_pct=50.0, foreign_net=0.0):
    """Simple transparent market-risk regime. Inputs must be current or explicitly delayed."""
    idx=_safe_num(index_change_pct); breadth=_safe_num(breadth_pct,50); f=_safe_num(foreign_net)
    risk=0
    if idx <= -2.0: risk += 2
    elif idx <= -1.0: risk += 1
    if breadth < 30: risk += 2
    elif breadth < 42: risk += 1
    if f < 0: risk += 1
    return "RISK-OFF" if risk >= 4 else "CAUTION" if risk >= 2 else "NORMAL"

def stale_data_penalty(age_seconds=None, confidence="DAILY/DELAYED"):
    """Penalize stale/low-confidence data instead of pretending it is live."""
    p=0
    if confidence=="DAILY/DELAYED": p += 12
    elif confidence=="LIVE-MED": p += 5
    if age_seconds is not None:
        a=_safe_num(age_seconds)
        if a > 300: p += 12
        elif a > 120: p += 7
        elif a > 30: p += 3
    return p

def risk_adjusted_day_score(row, regime="NORMAL", age_seconds=None):
    d=strategy_scores(row)["단타점수"]
    conf=data_confidence(row)
    d -= stale_data_penalty(age_seconds, conf)
    if regime=="RISK-OFF": d -= 18
    elif regime=="CAUTION": d -= 8
    return round(float(np.clip(d,0,100)),1)

def position_plan(entry, stop, account_cash, risk_pct=0.005, max_position_pct=0.15):
    """Size a position from maximum account loss and concentration cap."""
    entry=_safe_num(entry); stop=_safe_num(stop); cash=_safe_num(account_cash)
    if entry<=0 or stop<=0 or stop>=entry or cash<=0:
        return {"수량":0,"투입금":0,"최대손실":0}
    per_share=entry-stop
    risk_budget=max(0,cash*max(0,min(risk_pct,0.03)))
    qty_risk=int(risk_budget//per_share)
    qty_cap=int((cash*max(0,min(max_position_pct,1.0)))//entry)
    qty=max(0,min(qty_risk,qty_cap))
    return {"수량":qty,"투입금":round(qty*entry),"최대손실":round(qty*per_share)}

def duplicate_signal_guard(history, code, now_ts, cooldown_minutes=15):
    """Avoid repeatedly surfacing the same unchanged ticker during a short cooldown."""
    if history is None or len(history)==0:return False
    try:
        h=history[history["code"].astype(str)==str(code)].copy()
        if len(h)==0:return False
        ts=pd.to_datetime(h["scan_time_utc"],utc=True,errors="coerce").dropna()
        if len(ts)==0:return False
        now=pd.Timestamp(now_ts)
        if now.tzinfo is None: now=now.tz_localize("UTC")
        return ((now-ts.max()).total_seconds()/60) < cooldown_minutes
    except Exception:
        return False

def audit_export_bytes():
    """Downloadable audit backup for Streamlit environments with ephemeral local storage."""
    return AUDIT_FILE.read_bytes() if AUDIT_FILE.exists() else b""

def audit_restore_bytes(data):
    """Validate a user-owned audit backup before replacing the current history."""
    if not data or len(data)>10*1024*1024:return False
    try:
        from io import BytesIO
        frame=pd.read_csv(BytesIO(data),dtype={"code":str})
        required={"scan_time_utc","code","price","stop","tp1"}
        if not required.issubset(frame.columns) or frame.empty:return False
        if pd.to_datetime(frame["scan_time_utc"],utc=True,errors="coerce").isna().any():return False
        for column in ["price","stop","tp1"]:
            values=pd.to_numeric(frame[column],errors="coerce")
            if values.isna().any() or not np.isfinite(values).all() or (values<=0).any():return False
        AUDIT_DIR.mkdir(parents=True,exist_ok=True)
        temporary=AUDIT_FILE.with_suffix(".tmp")
        temporary.write_bytes(frame.to_csv(index=False).encode("utf-8-sig"))
        temporary.replace(AUDIT_FILE)
        st.session_state.performance_verified=False
        return True
    except Exception:return False


# ============================================================
# DEPLOYMENT SELF-TEST
# ============================================================
def deployment_self_test():
    """Non-trading diagnostics. Never prints secrets."""
    result=[]
    # dependencies / runtime
    result.append(("Python/Streamlit runtime", True, "OK"))
    try:
        has_key=bool(st.secrets.get("KIS_APP_KEY",""))
        has_secret=bool(st.secrets.get("KIS_APP_SECRET",""))
        result.append(("KIS secrets", has_key and has_secret, "설정됨" if has_key and has_secret else "Secrets에 Key/Secret 필요"))
    except Exception:
        result.append(("KIS secrets", False, "Secrets 읽기 실패"))
    result.append(("Audit storage", AUDIT_DIR.exists(), str(AUDIT_DIR)))
    # Verify required scanner functions exist in this build.
    for fn in ("strategy_scores","actionable_levels","position_plan","save_scan_snapshot"):
        result.append((fn, callable(globals().get(fn)), "OK" if callable(globals().get(fn)) else "MISSING"))
    return pd.DataFrame(result,columns=["검사","통과","상태"])


# ============================================================
# LIVE FAIL-SAFE / HEALTH LAYER
# ============================================================
def live_health(last_update_utc=None, rest_ok=True, websocket_ok=True, investor_ok=True):
    """Health state used to suppress aggressive signals when live feeds degrade."""
    age=None
    if last_update_utc:
        try:
            ts=pd.Timestamp(last_update_utc)
            if ts.tzinfo is None: ts=ts.tz_localize("UTC")
            age=(pd.Timestamp.now(tz="UTC")-ts).total_seconds()
        except Exception:
            age=None
    issues=[]
    if not rest_ok: issues.append("REST")
    if not websocket_ok: issues.append("WS")
    if not investor_ok: issues.append("FLOW")
    if age is None or age<0 or age>120: issues.append("STALE")
    state="LIVE" if not issues else ("DEGRADED" if rest_ok else "OFFLINE")
    return {"state":state,"age_seconds":age,"issues":issues}

def fail_safe_score(row, health=None, regime="NORMAL"):
    """Never upgrade a score because data is missing; degraded feeds only reduce conviction."""
    h=health or {"state":"OFFLINE","age_seconds":None,"issues":["UNKNOWN"]}
    score=risk_adjusted_day_score(row,regime,h.get("age_seconds"))
    if h.get("state")=="DEGRADED": score-=12
    elif h.get("state")=="OFFLINE": score-=28
    return round(float(np.clip(score,0,100)),1)

def timestamp_fresh(value,seconds=120):
    stamp=pd.to_datetime(value,utc=True,errors="coerce")
    return bool(pd.notna(stamp) and 0<=(pd.Timestamp.now(tz="UTC")-stamp).total_seconds()<=seconds)

def row_live_health(row):
    return live_health(row.get("quote_received_utc"),timestamp_fresh(row.get("rest_received_utc")),
                       timestamp_fresh(row.get("trade_received_utc")) and timestamp_fresh(row.get("book_received_utc")),
                       timestamp_fresh(row.get("program_received_utc")))

def entry_risk_reason(row):
    change=_safe_num(row.get("등락률",row.get("등락%",0)))
    separation=_safe_num(row.get("20일이격",100),100)
    rsi=_safe_num(row.get("RSI",50),50)
    if change>=15 or separation>=115 or rsi>=80:
        return "과열·추격 위험"
    ask=_safe_num(row.get("매도1"));bid=_safe_num(row.get("매수1"))
    if ask<=0 or bid<=0 or ask<bid:return "유효한 최우선 호가 없음"
    if (ask-bid)/((ask+bid)/2)>.003:return "호가 간격 0.3% 초과"
    if entry_quality(row)["비용반영손익비"]<1.5:return "비용·저항 반영 손익비 1.5 미만"
    return ""

def entry_quality(row):
    levels=actionable_levels(row)
    entry=_safe_num(row.get("매도1")) or _safe_num(levels.get("매수관심상단"))
    stop=_safe_num(levels.get("손절기준"));target=_safe_num(levels.get("1차익절"))
    resistance=_safe_num(row.get("저항"))
    capped=entry<resistance<target
    if capped:target=resistance
    cost=entry*.004
    risk=entry-stop+cost
    ratio=max(0,(target-entry-cost)/risk) if entry>stop>0 and risk>0 else 0
    return {"비용반영손익비":round(ratio,2),"진입검토목표":target,
            "목표근거":"최근 20일 고가 저항" if capped else "ATR 시나리오·도달 미검증",
            "왕복비용가정%":0.4}

class HoldingNameCatalog:
    """An optional directory lookup must never hold up the app's main thread."""
    def __init__(self):
        self.lock=threading.Lock()
        self.names={"000660":"SK하이닉스","002995":"금호건설우","005930":"삼성전자"}
        self.started=False
        self.status="준비"
    def snapshot(self,loader):
        with self.lock:
            if not self.started:
                self.started=True
                self.status="목록 조회 중 · 화면 사용 가능"
                threading.Thread(target=self._load,args=(loader,),daemon=True).start()
            return dict(self.names),self.status
    def _load(self,loader):
        try:
            frame=loader()
            if "Code" not in frame and "Symbol" in frame:frame=frame.rename(columns={"Symbol":"Code"})
            if not {"Code","Name"}.issubset(frame.columns) or frame.empty:raise ValueError("empty directory")
            names=dict(zip(frame["Code"].astype(str).str.zfill(6),frame["Name"].astype(str)))
            with self.lock:
                self.names.update(names)
                self.status="종목명 목록 준비 완료"
        except Exception:
            with self.lock:self.status="종목명 목록 조회 실패 · 직접 입력 가능"

@st.cache_resource
def holding_name_catalog():
    return HoldingNameCatalog()

def fill_holding_names(frame, names):
    out=frame.copy()
    for idx,row in out.iterrows():
        code=str(row.get("코드","")).strip()
        if code in names:out.at[idx,"종목"]=names[code]
    return out

def holdings_editor_changed(key):
    base=st.session_state.holdings_draft.copy()
    changes=st.session_state.get(key,{})
    for idx,values in changes.get("edited_rows",{}).items():
        for col,value in values.items():base.at[int(idx),col]=value
    for row in changes.get("added_rows",[]):
        base=pd.concat([base,pd.DataFrame([row])],ignore_index=True)
    base=base.drop(index=changes.get("deleted_rows",[])).reset_index(drop=True)
    st.session_state.holdings_draft=fill_holding_names(base,st.session_state.get("holdings_names",{}))
    st.session_state.holdings_editor_revision=st.session_state.get("holdings_editor_revision",0)+1

def validate_holdings(frame):
    required=["코드","종목","수량","평단","손절가","익절가"]
    if not isinstance(frame,pd.DataFrame) or not all(c in frame for c in required[:4]):
        raise ValueError("보유종목 필수 열 확인 필요")
    frame=frame.dropna(how="all").copy()
    for col in ["손절가","익절가"]:
        if col not in frame:frame[col]=0
    out=frame[required].dropna(how="all").copy()
    if len(out)>5:raise ValueError("최대 5종목")
    codes=out["코드"].astype(str).str.strip()
    numbers=out[["수량","평단","손절가","익절가"]].apply(pd.to_numeric,errors="coerce")
    valid_codes=codes.map(lambda x:len(x)==6 and x.isascii() and x.isdigit()).all() and not codes.duplicated().any()
    numbers[["손절가","익절가"]]=numbers[["손절가","익절가"]].fillna(0)
    valid_numbers=np.isfinite(numbers.to_numpy(dtype=float)).all()
    valid_levels=((numbers["수량"]>0)&(numbers["수량"]%1==0)&(numbers["평단"]>0)&
                  (numbers["손절가"]>=0)&(numbers["익절가"]>=0)).all()
    if not valid_codes or not valid_numbers or not valid_levels:
        raise ValueError("중복 없는 6자리 코드·양의 정수 수량·양의 평단 확인 필요")
    out["코드"]=codes;out[numbers.columns]=numbers
    return out

def holding_chart_plan(row):
    close=_safe_num(row.get("종가"));volatility=_safe_num(row.get("ATR"))
    stamp=pd.to_datetime(row.get("기술기준일"),utc=True,errors="coerce")
    age=(pd.Timestamp.now(tz="UTC")-stamp).total_seconds() if not pd.isna(stamp) else float("inf")
    if close<=0 or volatility<=0 or not 0<=age<=7*86400:return {}
    support=_safe_num(row.get("지지"))
    stop=max(close*.01,min(close-volatility, support-volatility*.3 if support>0 else close-volatility))
    resistance=_safe_num(row.get("저항"))
    target=min(close+2*volatility,resistance) if resistance>close else close+2*volatility
    return {"손절가":round(stop),"익절가":round(target),"기술기준일":str(row.get("기술기준일")),
            "계산근거":"20일 지지·저항 및 ATR · 일봉 기준 고정 시나리오", "분석시각":pd.Timestamp.now(tz="UTC").isoformat()}

def holding_review(position, quote, plan=None):
    plan=plan or {}
    position=dict(position)
    if plan:
        position.update({k:plan[k] for k in ["손절가","익절가"]})
    qty=_safe_num(position.get("수량"));avg=_safe_num(position.get("평단"))
    px=_safe_num(quote.get("현재가"))
    stop=_safe_num(position.get("손절가"));target=_safe_num(position.get("익절가"))
    fresh=timestamp_fresh(quote.get("trade_received_utc"),seconds=30) and px>0
    out={"코드":position.get("코드"),"종목":position.get("종목"),"수량":qty,"평단":avg,
         "현재가":px if fresh else None,"평가손익":round((px-avg)*qty,2) if fresh and avg>0 else None,
         "수익률%":round((px/avg-1)*100,2) if fresh and avg>0 else None,
         "손절가":stop,"익절가":target,"체결시각":quote.get("체결시간","미수신"),
         "수신상태":"30초 이내 실제 체결" if fresh else "체결 미수신·30초 초과·가격 오류",
         "호가수신":"확인" if timestamp_fresh(quote.get("book_received_utc"),30) else "미확인",
         "프로그램수신":"확인" if timestamp_fresh(quote.get("program_received_utc"),120) else "미확인",
         "의견":"판단 보류","근거":"실제 체결 시각 확인 필요"}
    if not fresh:return out
    out["기술기준일"]=plan.get("기술기준일","미분석")
    out["자동기준근거"]=plan.get("계산근거","차트 기준 분석 필요")
    out["목표대비평단%"] = round((target/avg-1)*100,2) if avg>0 and target>0 else None
    out["종합검증"]="외국인·기관·뉴스·공시·지수 종합 검증 미완료"
    if qty<=0 or avg<=0 or not 0<stop<target:
        out["근거"]="보유종목 차트 기준을 분석하세요. 시세 감시는 계속합니다.";return out
    if px<=stop:out.update(의견="손절 조건 충족",근거="등록한 손절가 이하 · 실제 주문 체결 확인 필요")
    elif px>=target:
        out.update(의견="일부 익절 검토" if px>avg else "손실 축소 검토",
                   근거="차트 목표 구간 도달 · 평단을 넘지 않으면 익절이 아닙니다")
    else:out.update(의견="보유 관찰",근거="등록한 가격 조건 사이 · 수급·뉴스 종합판단은 미검증")
    if out["의견"]=="보유 관찰" and timestamp_fresh(quote.get("program_received_utc"),120) and timestamp_fresh(quote.get("book_received_utc"),30):
        if _safe_num(quote.get("프로그램"))<0 and _safe_num(quote.get("호가불균형"))<0:
            out.update(의견="수급 약화 점검",근거="프로그램 순매도·호가 불균형 음수 동시 확인 · 단독 매도 확정 근거 아님")
    return out

def entry_gate_reason(row):
    missing=[]
    for field,label in (("quote_received_utc","현재가"),("rest_received_utc","REST"),
                        ("trade_received_utc","체결"),("book_received_utc","호가"),
                        ("program_received_utc","프로그램")):
        if not timestamp_fresh(row.get(field)):missing.append(label)
    reasons=[]
    if missing:reasons.append("최근 수신 미확인: "+"·".join(missing))
    risk=entry_risk_reason(row)
    if risk:reasons.append(risk)
    if not reasons:
        status=execution_permission(row,row_live_health(row))
        reasons.append("진입 조건 통과 · 실전 성적 검증 중" if status=="진입확인" else "점수 기준 미달 · 관찰")
    return " / ".join(reasons)

def current_entry_view(frame):
    out=frame.copy()
    if out.empty:return out
    out["상태"]=[execution_permission(r,row_live_health(r)) for _,r in out.iterrows()]
    out["진입제한사유"]=[entry_gate_reason(r) for _,r in out.iterrows()]
    if kr_market_session_safe()=="CLOSED":
        out["상태"]="신규진입금지"
        out["진입제한사유"]="거래시간 외·등록 휴장일 / "+out["진입제한사유"]
    return out

def execution_permission(row, health=None, regime="NORMAL"):
    """Decision-support gate; does not place orders."""
    h=health or {"state":"OFFLINE"}
    score=fail_safe_score(row,h,regime)
    if h.get("state")!="LIVE" or data_confidence(row)=="DAILY/DELAYED":
        return "신규진입금지"
    if entry_risk_reason(row):return "신규진입금지"
    if regime=="RISK-OFF" and score<88:
        return "신규진입금지"
    if score>=82 and data_confidence(row)!="DAILY/DELAYED":
        return "진입확인"
    if score>=70:
        return "관심"
    return "대기"

def safe_call(fn, *args, default=None, **kwargs):
    """Prevent a single API/network failure from crashing the whole dashboard."""
    try:
        return fn(*args,**kwargs)
    except Exception:
        return default


# ============================================================
# ANALYSIS INTEGRITY / ANOMALY LAYER
# ============================================================
def validate_market_row(row):
    """Reject impossible or suspicious market rows before they can become a trade signal."""
    issues=[]
    px=_safe_num(row.get("현재가",row.get("종가",0)))
    close=_safe_num(row.get("종가",px))
    vol=_safe_num(row.get("장중거래량",row.get("거래량",0)))
    value=_safe_num(row.get("장중거래대금",row.get("거래대금",0)))
    ch=_safe_num(row.get("장중등락%",row.get("등락%",row.get("등락률",row.get("등락%",0)))))
    bid=_safe_num(row.get("매수1",0)); ask=_safe_num(row.get("매도1",0))

    if px<=0: issues.append("PRICE_INVALID")
    if close<=0: issues.append("CLOSE_INVALID")
    if vol<0 or value<0: issues.append("LIQUIDITY_INVALID")
    # Korean equities normally cannot exceed daily price limits; allow margin for source quirks.
    if abs(ch)>35: issues.append("CHANGE_OUTLIER")
    if bid>0 and ask>0 and bid>ask: issues.append("BOOK_CROSSED")
    if px>0 and close>0 and (px/close>1.5 or px/close<0.5): issues.append("PRICE_SCALE_MISMATCH")
    return {"valid":not issues,"issues":issues}

def source_coverage(row):
    """Be explicit about what evidence is actually present in the score."""
    tech=all(k in row for k in ("RSI","거래량x"))
    live=data_confidence(row)!="DAILY/DELAYED"
    flow=any(k in row for k in ("외국인","기관","프로그램","외국인순매수","기관순매수"))
    # News/disclosure connectors are not yet part of this local Streamlit build.
    return {
        "기술":bool(tech),
        "실시간시세":bool(live),
        "수급":bool(flow),
        "뉴스":_safe_num(row.get("뉴스건수"))>0,
        "공시":_safe_num(row.get("공시건수"))>0,
    }

def integrity_adjusted_score(row, regime="NORMAL", health=None):
    check=validate_market_row(row)
    if not check["valid"]:
        return 0.0
    score=fail_safe_score(row,health,regime)
    coverage=source_coverage(row)
    # Never reward missing evidence. Reduce conviction until the source is truly integrated.
    if not coverage["수급"]: score-=6
    if not coverage["뉴스"]: score-=3
    if not coverage["공시"]: score-=3
    return round(float(np.clip(score,0,100)),1)

def integrity_status(row):
    check=validate_market_row(row)
    if not check["valid"]:
        return "데이터격리:" + ",".join(check["issues"])
    c=source_coverage(row)
    missing=[k for k,v in c.items() if not v]
    dart_status=str(row.get("공시조회상태",""))
    notes=[]
    if dart_status in ("PASS","NO_DISCLOSURES"):
        missing=[k for k in missing if k!="공시"]
        if not c["공시"]:notes.append("공시:최근2일 없음")
    elif dart_status:
        missing=[k for k in missing if k!="공시"]
        labels={"NOT_QUERIED":"미조회","NO_MAPPING":"종목매핑 없음","NOT_CONFIGURED":"키 미설정","API_ERROR":"API 오류","REQUEST_ERROR":"요청 실패"}
        notes.append("공시:"+labels.get(dart_status,"조회 미확인"))
    base="정상" if not missing else "미연결:" + ",".join(missing)
    return " · ".join([base]+notes)


# ============================================================
# CATALYST / DISCLOSURE EVIDENCE LAYER
# ============================================================
POSITIVE_CATALYST_WORDS=("수주","공급계약","신규계약","흑자전환","상향","증설","승인","허가","자사주","배당","특허","협력","MOU")
NEGATIVE_CATALYST_WORDS=("유상증자","전환사채","CB","BW","적자전환","하향","소송","제재","리콜","횡령","배임","상장폐지","의견거절","한정의견","부적정의견","계약해지","계약 해지","수주취소","수주 취소","자사주처분","자사주 처분","거래정지")

def catalyst_text_score(title="", body="", source_type="news"):
    """Transparent keyword evidence score. It never fabricates a catalyst."""
    text=(str(title)+" "+str(body)).strip()
    if not text:return {"score":0,"positive":[],"negative":[]}
    import re
    def matches(word):
        if word in ("CB","BW","MOU"):return bool(re.search(r"(?<![A-Za-z])"+word+r"(?![A-Za-z])",text,re.I))
        return word.lower() in text.lower()
    pos=[w for w in POSITIVE_CATALYST_WORDS if matches(w)]
    neg=[w for w in NEGATIVE_CATALYST_WORDS if matches(w)]
    weight=1.3 if source_type=="dart" else 1.0
    raw=(len(pos)*6-len(neg)*8)*weight
    if neg:raw=min(raw,-8*weight)
    return {"score":round(float(np.clip(raw,-30,30)),1),"positive":pos,"negative":neg}

def catalyst_bundle(items):
    """Combine only supplied evidence; newer/live fetching is handled by connectors/feed adapters."""
    if not items:return {"score":0.0,"count":0,"positive":[],"negative":[]}
    total=0; pos=[]; neg=[]
    for item in items:
        z=catalyst_text_score(item.get("title",""),item.get("body",""),item.get("type","news"))
        total+=z["score"]; pos+=z["positive"]; neg+=z["negative"]
    return {"score":round(float(np.clip(total,-35,35)),1),"count":len(items),
            "positive":sorted(set(pos)),"negative":sorted(set(neg))}

def apply_catalyst_score(row, evidence_items=None):
    """Catalyst score is zero unless real evidence was supplied."""
    z=catalyst_bundle(evidence_items or [])
    base=_safe_num(row.get("실시간단타점수",row.get("단타점수",0)))
    # Cap catalyst contribution so headlines cannot overpower liquidity/risk.
    final=base+z["score"]*.35
    return round(float(np.clip(final,0,100)),1),z

def disclosure_feed_status():
    """Describe feed readiness without pretending a feed is live."""
    try:
        dart_key=bool(st.secrets.get("DART_API_KEY",""))
    except Exception:
        dart_key=False
    return {"DART":"READY" if dart_key else "NOT_CONFIGURED",
            "NEWS":"ADAPTER_REQUIRED"}

def dart_recent_disclosures(corp_code, days=2, max_count=20):
    """Official OpenDART adapter. Requires user's DART_API_KEY in Streamlit Secrets."""
    try:
        key=st.secrets.get("DART_API_KEY","")
    except Exception:
        key=""
    diagnostics=st.session_state.setdefault("feed_diagnostics",{})
    st.session_state.dart_live_verified=False
    if not key or not corp_code:
        diagnostics["DART_DISCLOSURES"]={"status":"NOT_CONFIGURED" if not key else "NO_MAPPING"}
        return []
    try:
        end=pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y%m%d")
        begin=(pd.Timestamp.now(tz="Asia/Seoul")-pd.Timedelta(days=max(1,days))).strftime("%Y%m%d")
        r=requests.get("https://opendart.fss.or.kr/api/list.json",
            params={"crtfc_key":key,"corp_code":str(corp_code),"bgn_de":begin,"end_de":end,"page_count":max_count},
            timeout=8)
        r.raise_for_status(); payload=r.json()
        status=str(payload.get("status","UNKNOWN"))
        diagnostics["DART_DISCLOSURES"]={"status":"PASS" if status=="000" else "NO_DISCLOSURES" if status=="013" else "API_ERROR",
            "api_status":status,"조회시작":begin,"조회종료":end,"건수":len(payload.get("list",[]) or [])}
        if status not in ("000","013"):return []
        st.session_state.dart_live_verified=True
        out=[]
        for x in payload.get("list",[]) or []:
            out.append({"type":"dart","title":x.get("report_nm",""),"body":x.get("corp_name",""),
                        "date":x.get("rcept_dt",""),"receipt":x.get("rcept_no","")})
        return out
    except Exception as exc:
        diagnostics["DART_DISCLOSURES"]={"status":"REQUEST_ERROR","error_type":type(exc).__name__}
        return []


# ============================================================
# DART CORP-CODE MAP / RATE-SAFE CATALYST CACHE
# ============================================================
_DART_CORP_MAP=st.session_state.setdefault("dart_corp_map",{})
_DART_CACHE=st.session_state.setdefault("dart_cache",{})

def dart_corp_map_status():
    return {"count":len(_DART_CORP_MAP),"ready":bool(_DART_CORP_MAP)}

def load_dart_corp_map_csv(data):
    """Load a user-owned KRX-code -> DART corp_code CSV without exposing credentials.
    Accepted columns: stock_code,corp_code or 종목코드,고유번호.
    """
    global _DART_CORP_MAP
    try:
        from io import BytesIO
        df=pd.read_csv(BytesIO(data),dtype=str)
        stock_col="stock_code" if "stock_code" in df.columns else "종목코드" if "종목코드" in df.columns else None
        corp_col="corp_code" if "corp_code" in df.columns else "고유번호" if "고유번호" in df.columns else None
        if not stock_col or not corp_col:return False
        m={}
        for _,r in df[[stock_col,corp_col]].dropna().iterrows():
            stock=str(r[stock_col]).strip().zfill(6)
            corp=str(r[corp_col]).strip().zfill(8)
            if stock.isdigit() and corp.isdigit():m[stock]=corp
        if not m:return False
        _DART_CORP_MAP=m
        st.session_state.dart_corp_map=m
        return True
    except Exception:
        return False

def dart_corp_code(stock_code):
    return _DART_CORP_MAP.get(str(stock_code).zfill(6))

def cached_dart_disclosures(stock_code, days=2, ttl_seconds=300):
    """Rate-safe DART lookup. No mapping/no key -> empty evidence, never guessed evidence."""
    import time
    code=str(stock_code).zfill(6)
    corp=dart_corp_code(code)
    if not corp:return []
    key=(code,int(days))
    now=time.time()
    hit=_DART_CACHE.get(key)
    if hit and now-hit["time"]<ttl_seconds:return hit["data"]
    data=dart_recent_disclosures(corp,days=days,max_count=20)
    status=st.session_state.get("feed_diagnostics",{}).get("DART_DISCLOSURES",{}).get("status","UNKNOWN")
    _DART_CACHE[key]={"time":now,"data":data,"status":status}
    return data

def attach_disclosure_evidence(df, top_n=30, days=2):
    """Query only top candidates to protect latency/API quota, then re-rank with real DART evidence."""
    if df is None or len(df)==0:return df
    out=df.copy()
    out["공시점수"]=0.0
    out["공시건수"]=0
    if "실시간단타점수" in out.columns:
        out["실시간단타점수"]=pd.to_numeric(out["실시간단타점수"],errors="coerce").fillna(0).astype(float)
    out["공시근거"]=""
    out["공시조회상태"]="NOT_QUERIED"
    limit=min(max(int(top_n),0),len(out))
    for idx in out.head(limit).index:
        r=out.loc[idx]
        code=r.get("코드",r.get("Code",""))
        items=cached_dart_disclosures(code,days=days)
        hit=_DART_CACHE.get((str(code).zfill(6),int(days)),{})
        out.at[idx,"공시조회상태"]=hit.get("status","NO_MAPPING" if not dart_corp_code(code) else "UNKNOWN")
        z=catalyst_bundle(items)
        out.at[idx,"공시점수"]=z["score"]
        out.at[idx,"공시건수"]=z["count"]
        out.at[idx,"공시근거"]=" / ".join((z["positive"]+z["negative"])[:6])
        base=_safe_num(out.at[idx,"실시간단타점수"] if "실시간단타점수" in out.columns else r.get("단타점수",0))
        out.at[idx,"실시간단타점수"]=round(float(np.clip(base+z["score"]*.35,0,100)),1)
    return out.sort_values(["실시간단타점수","단타점수","점수"],ascending=False)


# ============================================================
# NEWS EVIDENCE ADAPTER (USER/FEED SUPPLIED, TIMESTAMP-AWARE)
# ============================================================
_NEWS_CACHE=st.session_state.setdefault("news_cache",[])

def load_news_feed_csv(data):
    """Load a timestamped news feed exported from a trusted provider.
    Required: title. Optional: published_at, source, body, stock_code, stock_name, url.
    This app does not scrape arbitrary sites or invent missing headlines.
    """
    global _NEWS_CACHE
    try:
        from io import BytesIO
        df=pd.read_csv(BytesIO(data),dtype=str).fillna("")
        if "title" not in df.columns:return False
        rows=[]
        for _,r in df.iterrows():
            x={k:str(r.get(k,"")).strip() for k in ("title","published_at","source","body","stock_code","stock_name","url")}
            if not x["title"]:continue
            if x["published_at"]:
                ts=pd.to_datetime(x["published_at"],utc=True,errors="coerce")
                x["_ts"]=ts.isoformat() if pd.notna(ts) else ""
            else:x["_ts"]=""
            rows.append(x)
        _NEWS_CACHE=rows
        st.session_state.news_cache=rows
        return bool(rows)
    except Exception:
        return False

def news_feed_status():
    return {"count":len(_NEWS_CACHE),"ready":bool(_NEWS_CACHE)}

def news_for_stock(stock_code="", stock_name="", max_age_hours=24, max_items=20):
    now=pd.Timestamp.now(tz="UTC")
    code=str(stock_code).zfill(6) if str(stock_code).strip() else ""
    name=str(stock_name).strip()
    out=[]
    for x in _NEWS_CACHE:
        # Require explicit stock code/name match; no fuzzy hallucinated association.
        matched=(code and str(x.get("stock_code","")).zfill(6)==code) or (name and name in (x.get("title","")+" "+x.get("body","")+" "+x.get("stock_name","")))
        if not matched:continue
        ts=pd.to_datetime(x.get("_ts"),utc=True,errors="coerce")
        if pd.isna(ts) or not 0 <= (now-ts).total_seconds() <= max_age_hours*3600:continue
        out.append({"type":"news","title":x.get("title",""),"body":x.get("body",""),
                    "source":x.get("source",""),"published_at":x.get("_ts",""),"url":x.get("url","")})
        if len(out)>=max_items:break
    return out

def attach_news_evidence(df, top_n=30, max_age_hours=24):
    if df is None or len(df)==0:return df
    out=df.copy()
    out["뉴스점수"]=0.0; out["뉴스건수"]=0; out["뉴스근거"]=""
    if "실시간단타점수" in out.columns:
        out["실시간단타점수"]=pd.to_numeric(out["실시간단타점수"],errors="coerce").fillna(0).astype(float)
    for idx in out.head(min(max(int(top_n),0),len(out))).index:
        r=out.loc[idx]
        items=news_for_stock(r.get("코드",r.get("Code","")),r.get("종목",r.get("종목명",r.get("Name",""))),max_age_hours)
        z=catalyst_bundle(items)
        out.at[idx,"뉴스점수"]=z["score"]; out.at[idx,"뉴스건수"]=z["count"]
        out.at[idx,"뉴스근거"]=" / ".join((z["positive"]+z["negative"])[:6])
        base=_safe_num(out.at[idx,"실시간단타점수"] if "실시간단타점수" in out.columns else r.get("단타점수",0))
        # News gets lower weight than official DART disclosures.
        out.at[idx,"실시간단타점수"]=round(float(np.clip(base+z["score"]*.20,0,100)),1)
    return out.sort_values(["실시간단타점수","단타점수","점수"],ascending=False)


# ============================================================
# FOCUSED LIVE RERANK (TOP CANDIDATES)
# ============================================================
# ============================================================
# RATE-SAFE ROTATING LIVE REFRESH / MARKET SESSION GUARD
# ============================================================
def kr_market_session(now_kst=None):
    """Broad Korean equity session guard including NXT/pre/after windows."""
    now=now_kst or pd.Timestamp.now(tz="Asia/Seoul")
    if not isinstance(now,pd.Timestamp): now=pd.Timestamp(now)
    now=now.tz_localize("Asia/Seoul") if now.tzinfo is None else now.tz_convert("Asia/Seoul")
    if now.weekday()>=5:return "CLOSED"
    hm=now.hour*60+now.minute
    if 8*60 <= hm < 9*60:return "PRE"
    if 9*60 <= hm < 15*60+30:return "REGULAR"
    if 15*60+30 <= hm < 20*60:return "AFTER"
    return "CLOSED"

def refresh_batch_indices(df, batch_size=8):
    """Rotate through candidates instead of hammering every symbol each refresh."""
    if df is None or len(df)==0:return []
    n=len(df); b=max(1,min(int(batch_size),n))
    cursor=int(st.session_state.get("live_cursor",0))%n
    pos=[(cursor+i)%n for i in range(b)]
    st.session_state.live_cursor=(cursor+b)%n
    return list(df.sort_index().index[pos])

def refresh_top_candidates_rate_safe(df, top_n=30, batch_size=8):
    if df is None or len(df)==0 or not kis_configured():return df
    session=kr_market_session_safe()
    if session=="CLOSED":return df
    out=df.copy(); focus=out.head(min(max(int(top_n),1),len(out))).copy()
    rotated=refresh_batch_indices(out,batch_size)
    if st.session_state.get("candidate_monitor_enabled"):
        # Keep top five REST evidence fresh while rotating the remaining request slots.
        cap=max(1,int(batch_size))
        priority=list(out.head(min(5,max(0,cap-1))).index)
        idxs=(priority+[idx for idx in rotated if idx not in priority])[:cap]
    else:idxs=rotated
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=min(4,len(idxs) or 1)) as ex:
        fut={ex.submit(kis_quote,str(out.loc[idx].get("코드","")).zfill(6)):idx for idx in idxs}
        for f in as_completed(fut):
            idx=fut[f]
            try:q=f.result()
            except Exception:q=None
            if not q:continue
            for k,v in q.items():out.at[idx,k]=v
            if q.get("현재가",0)>0:
                out.at[idx,"종가"]=q["현재가"]; out.at[idx,"등락%"]=q.get("장중등락%",out.loc[idx].get("등락%",0))
    tape=live_tape()
    if hasattr(tape,"snapshots"):
        tape_rows,tape_connected,tape_error=tape.snapshots()
    else:
        data,tape_connected,tape_error=tape.snapshot()
        tape_rows={data.get("코드"):data} if data else {}
    if tape_connected:
        for idx in out.index:
            data=tape_rows.get(str(out.at[idx,"코드"]).zfill(6),{})
            if timestamp_fresh(data.get("trade_received_utc")):
                for key,value in data.items():out.at[idx,key]=value
                if data.get("현재가",0)>0:
                    out.at[idx,"종가"]=data["현재가"];out.at[idx,"등락%"]=data.get("등락%",out.at[idx,"등락%"])
                if idx not in idxs:idxs.append(idx)
    out=refresh_technical_rows(out,idxs)
    # Recalculate all candidates using latest available data; only batch network calls rotate.
    out["현재가"]=pd.to_numeric(out["현재가"],errors="coerce").fillna(out["종가"]) if "현재가" in out.columns else pd.to_numeric(out["종가"],errors="coerce")
    out["거래대금"]=pd.to_numeric(out["장중거래대금"],errors="coerce").fillna(out.get("거래대금",0)) if "장중거래대금" in out.columns else out.get("거래대금",pd.Series(0.0,index=out.index))
    out["등락률"]=out["등락%"]
    out=enrich_scan_dataframe(out)
    out["분석무결성"]=[integrity_status(r.to_dict()) for _,r in out.iterrows()]
    out["실시간단타점수"]=[integrity_adjusted_score(r.to_dict(),"NORMAL",row_live_health(r)) for _,r in out.iterrows()]
    out["매수하단"]=out["매수관심하단"]; out["매수상단"]=out["매수관심상단"]; out["손절가"]=out["손절기준"]
    out["1차목표"]=out["1차익절"]; out["2차목표"]=out["2차익절"]
    return attach_all_evidence(out)


_KRX_HOLIDAYS=st.session_state.setdefault("krx_holidays",set())
def load_krx_holidays_csv(data):
    global _KRX_HOLIDAYS
    try:
        from io import BytesIO
        df=pd.read_csv(BytesIO(data),dtype=str)
        col="date" if "date" in df.columns else "일자" if "일자" in df.columns else None
        if not col:return False
        vals=set()
        for v in df[col].dropna():
            ts=pd.to_datetime(str(v),errors="coerce")
            if pd.notna(ts):vals.add(ts.strftime("%Y-%m-%d"))
        if not vals:return False
        _KRX_HOLIDAYS=vals; st.session_state.krx_holidays=vals; return True
    except Exception:return False
def krx_holiday_status(): return {"count":len(_KRX_HOLIDAYS),"configured":bool(_KRX_HOLIDAYS)}
def is_krx_holiday(now_kst=None):
    now=now_kst or pd.Timestamp.now(tz="Asia/Seoul")
    if not isinstance(now,pd.Timestamp):now=pd.Timestamp(now)
    now=now.tz_localize("Asia/Seoul") if now.tzinfo is None else now.tz_convert("Asia/Seoul")
    return now.strftime("%Y-%m-%d") in _KRX_HOLIDAYS
def kr_market_session_safe(now_kst=None):
    now=now_kst or pd.Timestamp.now(tz="Asia/Seoul")
    if not isinstance(now,pd.Timestamp):now=pd.Timestamp(now)
    now=now.tz_localize("Asia/Seoul") if now.tzinfo is None else now.tz_convert("Asia/Seoul")
    if now.weekday()>=5 or is_krx_holiday(now):return "CLOSED"
    return kr_market_session(now)


# ============================================================
def build_id():
    root=Path(__file__).resolve().parent
    digest=hashlib.sha256()
    for name in ("app.py","feeds.py","scoring.py","ws_protocol.py","performance.py","requirements.txt"):
        digest.update(name.encode());digest.update((root/name).read_bytes())
    return digest.hexdigest()[:12]

def deployment_attestation_valid():
    proof=st.session_state.get("deploy_attestation",{})
    stamp=pd.to_datetime(proof.get("verified_utc"),utc=True,errors="coerce")
    return bool(proof.get("build_id")==build_id() and proof.get("app_url")=="https://sungho-stock-scanner-vwyfgmbbuipzpd3btyuh7r.streamlit.app/"
                and proof.get("visible_build_verified") is True and pd.notna(stamp)
                and 0<=(pd.Timestamp.now(tz="UTC")-stamp).total_seconds()<86400)

def secret_value(name):
    try:return str(st.secrets.get(name, ""))
    except Exception:return ""

def ensure_dart_map():
    global _DART_CORP_MAP
    diagnostics=st.session_state.setdefault("feed_diagnostics",{})
    if _DART_CORP_MAP:
        diagnostics["DART_MAPPING"]="PASS"
        return True
    if not secret_value("DART_API_KEY"):
        diagnostics["DART_MAPPING"]="NOT_CONFIGURED"
        return False
    try:
        for attempt in range(2):
            try:
                _DART_CORP_MAP=dart_corporations(secret_value("DART_API_KEY"))
                break
            except (requests.Timeout,requests.ConnectionError):
                if attempt:raise
        st.session_state.dart_corp_map=_DART_CORP_MAP
        st.session_state.setdefault("feed_diagnostics",{})["DART_MAPPING"]="PASS" if _DART_CORP_MAP else "EMPTY"
        return bool(_DART_CORP_MAP)
    except Exception as exc:
        st.session_state.setdefault("feed_diagnostics",{})["DART_MAPPING"]=str(exc) if isinstance(exc,FeedError) else type(exc).__name__
        return False

def refresh_news_candidates(frame,top_n=10,ttl=300):
    global _NEWS_CACHE
    client_id=secret_value("NAVER_CLIENT_ID");client_secret=secret_value("NAVER_CLIENT_SECRET")
    cache=st.session_state.setdefault("automatic_news",{})
    provider=(secret_value("NAVER_API_PROVIDER") or "LEGACY").strip().upper()
    identity=hashlib.sha256(json.dumps([provider,client_id,client_secret]).encode()).hexdigest()
    if st.session_state.get("automatic_news_identity")!=identity:
        cache.clear()
        _NEWS_CACHE=[x for x in _NEWS_CACHE if x.get("source")!="NAVER Search"]
        st.session_state.news_cache=_NEWS_CACHE
        st.session_state.automatic_news_identity=identity
    if not client_id or not client_secret:
        st.session_state.setdefault("feed_diagnostics",{})["NEWS"]="NOT_CONFIGURED: 네이버 뉴스 키 미설정"
        return
    if st.session_state.get("automatic_news_provider")!=provider:
        cache.clear()
        st.session_state.automatic_news_provider=provider
    for _,row in frame.head(top_n).iterrows():
        code=str(row.get("코드",""));name=str(row.get("종목",""))
        if not name:continue
        hit=cache.get(code,{})
        if time.time()-hit.get("time",0)<ttl:continue
        try:
            items=naver_news(name,code,client_id,client_secret,
                             provider=provider)
            cache[code]={"time":time.time(),"items":items}
            st.session_state.setdefault("feed_diagnostics",{})["NEWS"]="PASS_RESPONSE"
        except Exception as exc:
            st.session_state.setdefault("feed_diagnostics",{})["NEWS"]=type(exc).__name__
    manual=[x for x in _NEWS_CACHE if x.get("source")!="NAVER Search"]
    _NEWS_CACHE=manual+[x for hit in cache.values() for x in hit.get("items",[])]
    st.session_state.news_cache=_NEWS_CACHE

def refresh_technical_rows(frame,indices):
    out=frame.copy()
    end=business_day();start=end-dt.timedelta(days=240)
    for idx in indices:
        row=out.loc[idx].to_dict()
        if data_confidence(row)=="DAILY/DELAYED":continue
        history=prices(row.get("코드"),start.isoformat(),end.isoformat())
        if history is not None and not history.empty and not row.get("market_date"):
            row["market_date"]=pd.Timestamp(history.index[-1]).strftime("%Y%m%d")
        updated=overlay_quote(history,row)
        if updated is None or len(updated)<65:continue
        technical=analyze(row.get("코드"),row.get("종목",""),updated)
        if technical:
            for key,value in technical.items():out.at[idx,key]=value
            out.at[idx,"등락%"]=row.get("장중등락%",technical["등락%"])
            out.at[idx,"거래량비"]=technical.get("거래량x",1)
            out.at[idx,"20일이격"]=100+technical.get("20일이격%",0)
    return out

def attach_all_evidence(frame):
    if frame is None or frame.empty:return frame
    out=frame.copy()
    out["실시간단타점수"]=pd.to_numeric(out["실시간단타점수"],errors="coerce").fillna(0).astype(float)
    # Called after a new base score; reset all catalyst increments to prevent accumulation.
    for column in ["공시점수","공시건수","뉴스점수","뉴스건수"]:out[column]=0.0
    if ensure_dart_map():out=attach_disclosure_evidence(out,top_n=10)
    else:out["공시조회상태"]="NOT_CONFIGURED" if not secret_value("DART_API_KEY") else "NO_MAPPING"
    refresh_news_candidates(out)
    if news_feed_status().get("ready"):out=attach_news_evidence(out,top_n=10)
    out["분석무결성"]=[integrity_status(r.to_dict()) for _,r in out.iterrows()]
    for idx,row in out.iterrows():
        d=row.to_dict();health=row_live_health(d)
        base=integrity_adjusted_score(d,"NORMAL",health)
        out.at[idx,"실시간단타점수"]=round(float(np.clip(base+_safe_num(d.get("공시점수"))*.35+_safe_num(d.get("뉴스점수"))*.2,0,100)),1)
        out.at[idx,"상태"]=execution_permission(d,health)
    return out.sort_values(["실시간단타점수","단타점수","점수","거래대금x"],ascending=False)

# RELEASE READINESS GATE
# ============================================================
def release_readiness():
    """Deployment checklist. Never exposes secret values."""
    rows=[]
    try:
        kis_ok=bool(st.secrets.get("KIS_APP_KEY","")) and bool(st.secrets.get("KIS_APP_SECRET",""))
    except Exception:kis_ok=False
    try:
        dart_ok=bool(st.secrets.get("DART_API_KEY",""))
    except Exception:dart_ok=False
    rows += [
        {"항목":"KIS 인증정보","필수":True,"상태":"PASS" if kis_ok else "NEEDED"},
        {"항목":"WebSocket 패키지","필수":True,"상태":"PASS" if websocket_capability() else "NEEDED"},
        {"항목":"DART API","필수":False,"상태":"PASS" if dart_ok else "OPTIONAL"},
        {"항목":"DART 종목매핑","필수":False,"상태":"PASS" if dart_corp_map_status().get("ready") else "OPTIONAL"},
        {"항목":"뉴스피드","필수":False,"상태":"PASS" if news_feed_status().get("ready") else "OPTIONAL"},
        {"항목":"KRX 휴장일","필수":False,"상태":"PASS" if krx_holiday_status().get("configured") else "OPTIONAL"},
    ]
    required_pass=all(x["상태"]=="PASS" for x in rows if x["필수"])
    return pd.DataFrame(rows),required_pass

def live_release_gate():
    df,static_ok=release_readiness()
    q=kis_quote("005930") if kis_configured() else None
    if disclosure_feed_status().get("DART")=="READY":
        ensure_dart_map()
        corp=dart_corp_code("005930")
        st.session_state.dart_live_verified=False
        if corp:dart_recent_disclosures(corp)
    refresh_news_candidates(pd.DataFrame([{"코드":"005930","종목":"삼성전자"}]))
    data,connected,error=live_tape().snapshot()
    checks={
        "KIS REST":bool(q and _safe_num(q.get("현재가"))>0),
        "WebSocket 실제 체결·호가":bool(connected and timestamp_fresh(data.get("trade_received_utc")) and timestamp_fresh(data.get("book_received_utc"))),
        "DART 응답":bool(st.session_state.get("dart_live_verified")),
        "프로그램 실제 수신":timestamp_fresh(data.get("program_received_utc")),
        "뉴스 최신 근거":any(news_for_stock(x.get("stock_code"),x.get("stock_name")) for x in _NEWS_CACHE),
        "성적검증":bool(st.session_state.get("performance_verified") and st.session_state.get("performance_verified_build")==build_id()),
        "실제 배포 확인":deployment_attestation_valid(),
    }
    rows=pd.DataFrame([{"항목":k,"필수":True,"상태":"PASS" if v else "UNVERIFIED"} for k,v in checks.items()])
    return pd.concat([df,rows],ignore_index=True),static_ok,all(checks.values()),"미검증: "+", ".join(k for k,v in checks.items() if not v)

st.set_page_config(
    page_title="SUNGHO Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto"
)

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 5rem; max-width: 1280px;}
h1 {font-size: 2rem !important; margin-bottom: .3rem; letter-spacing: -.04em;}
h2, h3 {font-size: 1.25rem !important; letter-spacing: -.025em;}
.scanner-hero {display:flex; align-items:center; gap:16px; padding: 16px 20px; border-radius: 20px; background: linear-gradient(115deg,#101c33,#203e5d); color: #f8fafc; margin-bottom: 10px; box-shadow: 0 8px 24px rgba(15,23,42,.12);}
.scanner-hero .eyebrow {font-size: 12px; font-weight: 700; color: #d4bb82; letter-spacing: .16em; margin-bottom: 4px;}
.scanner-hero .brand {font-size: 23px; font-weight: 700; letter-spacing: -.04em; line-height: 1.3;}
.scanner-hero .description {font-size: 15px; color: #d1e0ee; margin-top: 4px; line-height: 1.6;}
div[data-testid="stExpander"] {border-radius: 16px; margin-top: 12px; border-color: rgba(128,128,128,.22);}
div[data-testid="stCaptionContainer"] p {font-size: 14px; line-height: 1.6; opacity: .95;}
div[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 14px;
    padding: 10px;
}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    font-size: 15px !important;
    color: var(--text-color) !important;
    opacity: .9;
    line-height: 1.5;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    font-size: 16px;
}
.owl-mark {width:48px; height:48px; flex-shrink:0; color:#d4bb82;}
.candidate-grid {display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; margin:8px 0 18px;}
.candidate-card {background:#142239; border:1px solid #30415a; border-radius:14px; padding:16px; color:#f1f5f9; min-width:0;}
.card-rank {color:#d4bb82; font-size:12px; font-weight:600; letter-spacing:.05em;}
.card-name {font-size:17px; font-weight:700; margin:10px 0 8px; overflow-wrap:anywhere;}
.card-price {font-size:22px; font-weight:700; font-variant-numeric:tabular-nums;}
.card-price span,.card-score span {font-size:12px; color:#b4c2d4;}
.card-change {font-size:16px; font-weight:600; margin:2px 0 12px;}
.card-change.up {color:#ff838b;} .card-change.down {color:#80b3ff;} .card-change.flat {color:#cbd5e1;}
.card-score {font-size:13px; color:#d5deea; border-top:1px solid #34445d; padding-top:10px;}
.card-score strong {font-size:20px; color:#f8fafc;}
.card-status {font-size:13px; margin-top:8px; font-weight:600;}
.card-reason {font-size:12px;line-height:1.5;color:#d7dfeb;margin-top:8px;overflow-wrap:anywhere;}
.card-source {font-size:12px; color:#b4c2d4; margin-top:4px;}
@media (max-width:1000px) {
    .candidate-grid {display:flex; overflow-x:auto; scroll-snap-type:x proximity; padding-bottom:8px;}
    .candidate-card {flex:0 0 190px; scroll-snap-align:start;}
}
.stButton > button {
    min-height: 48px;
    border-radius: 14px;
    font-weight: 700;
    width: 100%;
    transition: border-color .15s ease;
}
.stButton > button:hover {border-color: #377eb5;}
.stButton > button[kind="primary"] {background: #175f96; border-color: #175f96; color: white;}
div[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
@media (max-width: 700px) {
    .block-container {padding-left: .75rem; padding-right: .75rem; padding-top: .6rem;}
    h1 {font-size: 1.45rem !important;}
    .scanner-hero {padding: 14px; border-radius: 16px;}
    .scanner-hero .brand {font-size: 20px;}
    div[data-testid="column"] {min-width: 0 !important;}
}
</style>
""", unsafe_allow_html=True)

def market_date(zone="Asia/Seoul",now=None):
    stamp=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if stamp.tzinfo is None:raise ValueError("시각에는 시간대가 필요합니다")
    return stamp.tz_convert(zone).date()

def business_day(d=None):
    d = d or market_date()
    while d.weekday() >= 5 or d.isoformat() in _KRX_HOLIDAYS:
        d -= dt.timedelta(days=1)
    return d

def ymd(d): return d.strftime("%Y%m%d")

def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/period, adjust=False).mean()
    al = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)

def macd_osc(close):
    m = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    s = m.ewm(span=9, adjust=False).mean()
    return m-s

def atr(df, period=14):
    pc = df["종가"].shift(1)
    tr = pd.concat([
        df["고가"]-df["저가"],
        (df["고가"]-pc).abs(),
        (df["저가"]-pc).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

@st.cache_data(ttl=3600, show_spinner=False)
def listing():
    if fdr is None:
        return pd.DataFrame()
    try:
        df=fdr.StockListing("KRX").copy()
        if "Code" not in df.columns and "Symbol" in df.columns:
            df=df.rename(columns={"Symbol":"Code"})
        if "Name" not in df.columns and "Name" not in df:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=30, show_spinner=False)
def prices(t, start, end):
    if fdr is None:
        return pd.DataFrame()
    try:
        if str(t).isdigit() and kis_configured():
            official=kis_daily_history(str(t),start,end)
            if len(official)>=65:return official
        d=fdr.DataReader(str(t), start, end).copy()
        if d.empty: return d
        ren={"Open":"시가","High":"고가","Low":"저가","Close":"종가","Volume":"거래량","Change":"등락률"}
        d=d.rename(columns=ren)
        if "거래대금" not in d.columns:
            d["거래대금"]=d["종가"]*d["거래량"]
        return d
    except Exception:
        return pd.DataFrame()


def kis_configured():
    try:
        return bool(st.secrets.get("KIS_APP_KEY")) and bool(st.secrets.get("KIS_APP_SECRET"))
    except Exception:
        return False

@st.cache_resource(show_spinner=False)
def token_resources():
    return {}, threading.RLock()
_TOKEN_STORE,_TOKEN_LOCK=token_resources()


def kis_token(appkey, appsecret, force_refresh=False):
    import hashlib
    identity=hashlib.sha256((appkey+":"+appsecret).encode()).hexdigest()
    with _TOKEN_LOCK:
        return _kis_token_locked(appkey,appsecret,force_refresh,identity)

def _kis_token_locked(appkey, appsecret, force_refresh, identity):
    """Reuse OAuth token to avoid needless token issuance and rate-limit pressure."""
    import time
    _KIS_TOKEN_CACHE=_TOKEN_STORE.setdefault(identity,{"token":None,"expires_at":0.0})
    now=time.time()
    if (not force_refresh and _KIS_TOKEN_CACHE.get("token")
            and now < float(_KIS_TOKEN_CACHE.get("expires_at",0))-60):
        return _KIS_TOKEN_CACHE["token"]
    r=requests.post(
        "https://openapi.koreainvestment.com:9443/oauth2/tokenP",
        json={"grant_type":"client_credentials","appkey":appkey,"appsecret":appsecret},
        timeout=10,
    )
    r.raise_for_status()
    payload=r.json()
    token=payload.get("access_token")
    if not token:
        raise RuntimeError("KIS token response missing access_token")
    # KIS commonly returns access_token_token_expired as a timestamp; use conservative cache
    # when exact parsing is unavailable.
    expires_in=float(payload.get("expires_in") or 3600)
    _KIS_TOKEN_CACHE.update({"token":token,"expires_at":now+max(300,min(expires_in,86400))})
    return token


@st.cache_resource(show_spinner=False)
def rate_resources():
    return {"last":0.0},threading.Lock()

_RATE_STATE,_RATE_LOCK=rate_resources()

def kis_rate_wait():
    with _RATE_LOCK:
        wait=max(0,.15-(time.monotonic()-_RATE_STATE["last"]))
        if wait:time.sleep(wait)
        _RATE_STATE["last"]=time.monotonic()

def kis_get(url, headers, params, appkey, appsecret, timeout=8):
    """Authenticated GET with one token refresh on HTTP 401."""
    token=kis_token(appkey,appsecret)
    h=dict(headers); h["authorization"]=f"Bearer {token}"
    kis_rate_wait()
    r=requests.get(url,headers=h,params=params,timeout=timeout)
    if getattr(r,"status_code",None)==401:
        token=kis_token(appkey,appsecret,force_refresh=True)
        h["authorization"]=f"Bearer {token}"
        kis_rate_wait()
        r=requests.get(url,headers=h,params=params,timeout=timeout)
    r.raise_for_status()
    return r

def kis_market_code():
    value=secret_value("KIS_MARKET_DIV_CODE") or "UN"
    return value if value in ("J","NX","UN") else "UN"

def kis_quote(code):
    if not kis_configured():
        return None
    try:
        appkey=st.secrets["KIS_APP_KEY"]
        appsecret=st.secrets["KIS_APP_SECRET"]
        headers={"appkey":appkey,"appsecret":appsecret,"tr_id":"FHKST01010100","custtype":"P"}
        params={"FID_COND_MRKT_DIV_CODE":kis_market_code(),"FID_INPUT_ISCD":str(code).zfill(6)}
        r=kis_get(
            "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price",
            headers,params,appkey,appsecret,timeout=8)
        r.raise_for_status(); payload=r.json()
        if payload.get("rt_cd")!="0": return None
        o=payload.get("output",{})
        px=float(o.get("stck_prpr") or 0)
        vol=float(o.get("acml_vol") or 0)
        val=float(o.get("acml_tr_pbmn") or 0)
        chg=float(o.get("prdy_ctrt") or 0)
        return {"현재가":px,"장중등락%":chg,"장중거래량":vol,"장중거래대금":val,"quote_received_utc":pd.Timestamp.now(tz="UTC").isoformat(),"rest_received_utc":pd.Timestamp.now(tz="UTC").isoformat(),
                "장중시가":_safe_num(o.get("stck_oprc")),"장중고가":_safe_num(o.get("stck_hgpr")),"장중저가":_safe_num(o.get("stck_lwpr")),
                "market_date":o.get("stck_bsop_date", "")}
    except Exception:
        return None


def kis_chart_response(code,path,tr_id,params):
    if not kis_configured():return {}
    key=secret_value("KIS_APP_KEY");secret=secret_value("KIS_APP_SECRET")
    response=kis_get("https://openapi.koreainvestment.com:9443"+path,
                     {"appkey":key,"appsecret":secret,"tr_id":tr_id,"custtype":"P"},params,key,secret)
    payload=response.json()
    return payload if payload.get("rt_cd")=="0" else {}

@st.cache_data(ttl=30,show_spinner=False)
def kis_daily_history(code,start,end):
    rows=[];begin=pd.Timestamp(start).normalize();finish=pd.Timestamp(end).normalize()
    try:
        for page in range(4):
            params={"FID_COND_MRKT_DIV_CODE":kis_market_code(),"FID_INPUT_ISCD":str(code).zfill(6),
                    "FID_INPUT_DATE_1":begin.strftime("%Y%m%d"),"FID_INPUT_DATE_2":finish.strftime("%Y%m%d"),
                    "FID_PERIOD_DIV_CODE":"D","FID_ORG_ADJ_PRC":"0"}
            payload=kis_chart_response(code,"/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice","FHKST03010100",params)
            batch=[x for x in payload.get("output2",[]) if x.get("stck_bsop_date")]
            if not batch:break
            rows.extend(batch)
            earliest=min(pd.Timestamp(x["stck_bsop_date"]) for x in batch)
            if earliest<=begin or len(batch)<100:break
            new_finish=earliest-pd.Timedelta(days=1)
            if new_finish>=finish:break
            finish=new_finish
        if not rows:return pd.DataFrame()
        data=pd.DataFrame(rows).rename(columns={"stck_bsop_date":"date","stck_oprc":"시가","stck_hgpr":"고가","stck_lwpr":"저가","stck_clpr":"종가","acml_vol":"거래량","acml_tr_pbmn":"거래대금"})
        data["date"]=pd.to_datetime(data["date"],format="%Y%m%d",errors="coerce")
        data=data.dropna(subset=["date"]).drop_duplicates("date").set_index("date").sort_index()
        for column in ["시가","고가","저가","종가","거래량","거래대금"]:
            if column in data:data[column]=pd.to_numeric(data[column],errors="coerce")
        if "거래대금" not in data:data["거래대금"]=data["종가"]*data["거래량"]
        data=data.loc[pd.Timestamp(start):pd.Timestamp(end)].dropna(subset=["시가","고가","저가","종가","거래량"])
        data.attrs["source"]="KIS DAILY"
        return data
    except Exception:return pd.DataFrame()

@st.cache_data(ttl=15,show_spinner=False)
def kis_minute_history(code):
    try:
        params={"FID_COND_MRKT_DIV_CODE":kis_market_code(),"FID_INPUT_ISCD":str(code).zfill(6),"FID_INPUT_HOUR_1":pd.Timestamp.now(tz="Asia/Seoul").strftime("%H%M%S"),"FID_PW_DATA_INCU_YN":"Y","FID_ETC_CLS_CODE":""}
        payload=kis_chart_response(code,"/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice","FHKST03010200",params)
        data=pd.DataFrame(payload.get("output2",[]))
        if data.empty:return data
        data["time"]=pd.to_datetime(data["stck_bsop_date"]+data["stck_cntg_hour"],format="%Y%m%d%H%M%S",errors="coerce")
        data=data.rename(columns={"stck_oprc":"시가","stck_hgpr":"고가","stck_lwpr":"저가","stck_prpr":"종가","cntg_vol":"거래량"})
        for column in ["시가","고가","저가","종가","거래량"]:data[column]=pd.to_numeric(data[column],errors="coerce")
        data["거래대금"]=data["종가"]*data["거래량"]
        return data.dropna(subset=["time","종가"]).drop_duplicates("time").set_index("time").sort_index()
    except Exception:return pd.DataFrame()

@st.cache_data(ttl=3, show_spinner=False)
def kis_orderbook(code):
    """Top-of-book snapshot. Official REST fallback for live bid/ask."""
    if not kis_configured():
        return None
    try:
        appkey=st.secrets["KIS_APP_KEY"]; appsecret=st.secrets["KIS_APP_SECRET"]
        headers={"appkey":appkey,"appsecret":appsecret,"tr_id":"FHKST01010200","custtype":"P"}
        params={"FID_COND_MRKT_DIV_CODE":kis_market_code(),"FID_INPUT_ISCD":str(code).zfill(6)}
        r=kis_get(
            "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
            headers,params,appkey,appsecret,timeout=8)
        r.raise_for_status()
        o=r.json().get("output1",{}) or {}
        def num(k):
            try: return float(o.get(k) or 0)
            except Exception: return 0.0
        return {
            "매도1":num("askp1"), "매수1":num("bidp1"),
            "매도1잔량":num("askp_rsqn1"), "매수1잔량":num("bidp_rsqn1"),
            "총매도잔량":num("total_askp_rsqn"), "총매수잔량":num("total_bidp_rsqn"),
        }
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def kis_investor(code):
    """Investor history. KIS notes same-day figures are provided after market close."""
    if not kis_configured():
        return pd.DataFrame()
    try:
        appkey=st.secrets["KIS_APP_KEY"]; appsecret=st.secrets["KIS_APP_SECRET"]
        headers={"appkey":appkey,"appsecret":appsecret,"tr_id":"FHKST01010900","custtype":"P"}
        params={"FID_COND_MRKT_DIV_CODE":"J","FID_INPUT_ISCD":str(code).zfill(6)}
        r=kis_get(
            "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-investor",
            headers,params,appkey,appsecret,timeout=8)
        r.raise_for_status()
        rows=r.json().get("output",[]) or []
        if not rows: return pd.DataFrame()
        z=pd.DataFrame(rows)
        keep=["stck_bsop_date","prsn_ntby_qty","frgn_ntby_qty","orgn_ntby_qty"]
        if not all(c in z.columns for c in keep): return pd.DataFrame()
        z=z[keep].rename(columns={
            "stck_bsop_date":"일자","prsn_ntby_qty":"개인",
            "frgn_ntby_qty":"외국인","orgn_ntby_qty":"기관"})
        for c in ["개인","외국인","기관"]:
            z[c]=pd.to_numeric(z[c],errors="coerce").fillna(0)
        return z
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60,show_spinner=False)
def kis_estimated_investor(code):
    """Official intraday estimates, distinct from confirmed investor history."""
    if not kis_configured():return pd.DataFrame()
    try:
        key=secret_value("KIS_APP_KEY");secret=secret_value("KIS_APP_SECRET")
        response=kis_get("https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/investor-trend-estimate",
                         {"appkey":key,"appsecret":secret,"tr_id":"HHPTJ04160200","custtype":"P"},
                         {"MKSC_SHRN_ISCD":str(code).zfill(6)},key,secret)
        payload=response.json()
        if payload.get("rt_cd")!="0":return pd.DataFrame()
        rows=pd.DataFrame(payload.get("output2",[]))
        mapping={"bsop_hour_gb":"입력구분","frgn_fake_ntby_qty":"외국인 추정 순매수(주)",
                 "orgn_fake_ntby_qty":"기관 추정 순매수(주)","sum_fake_ntby_qty":"합산 추정 순매수(주)"}
        if rows.empty or not all(c in rows for c in mapping):return pd.DataFrame()
        out=rows[list(mapping)].rename(columns=mapping)
        for c in list(mapping.values())[1:]:out[c]=pd.to_numeric(out[c],errors="coerce")
        if out.iloc[:,1:].isna().any().any():return pd.DataFrame()
        out.attrs["received_utc"]=pd.Timestamp.now(tz="UTC").isoformat()
        out.attrs["source"]="KIS 장중 추정가집계 · 기준일 응답 미제공"
        return out
    except Exception:return pd.DataFrame()

@st.cache_resource(show_spinner=False)
def websocket_capability():
    """
    Return whether the optional websocket-client dependency is installed.
    The UI uses REST snapshots everywhere and exposes WebSocket streaming only
    when the deployment has the dependency and KIS credentials.
    """
    try:
        import websocket  # websocket-client
        return True
    except Exception:
        return False

def parse_futures_packet(message,expected_code):
    parts=message.split("|",3)
    if len(parts)!=4 or parts[0]!="0" or parts[1]!="H0MFCNT0":return []
    count=int(parts[2]);fields=parts[3].split("^")
    if count<1 or count>100 or len(fields)!=count*49:raise ValueError("invalid futures packet length")
    out=[]
    for n in range(count):
        f=fields[n*49:(n+1)*49]
        if f[0]!=expected_code:continue
        price=float(f[5]);change=float(f[4])
        if not np.isfinite(price) or price<=0 or not np.isfinite(change):raise ValueError("invalid futures price")
        if len(f[1])!=6 or not f[1].isdigit():raise ValueError("invalid futures time")
        if int(f[1][:2])>23 or int(f[1][2:4])>59 or int(f[1][4:])>59:raise ValueError("invalid futures time")
        out.append({"코드":f[0],"최근값":price,"전일대비%":change,"체결시간":f[1],
                    "수신시각":pd.Timestamp.now(tz="UTC").isoformat()})
    return out

@st.cache_resource(show_spinner=False)
def websocket_owners():
    return threading.Lock(), {}

class KISLiveTape:
    """Single socket, up to ten stock symbols, with isolated snapshots and reconnect."""
    def __init__(self):
        self.lock=threading.Lock()
        self.stop_event=threading.Event()
        self.thread=None
        self.ws=None
        self.code=None
        self.codes=()
        self.by_code={}
        self.approval=None
        self.channels=()
        self.subscription_lock=threading.RLock()
        self.market=None
        self.data={}
        self.error=""
        self.connected=False
        self.acknowledged=set()
        self.reconnect_count=0
        self.close_code=None
        self.subscription_code=""

    def snapshot(self, code=None):
        with self.lock:
            data=self.by_code.get(str(code).zfill(6),{}) if code is not None else self.data
            return dict(data), self.connected, self.error

    def snapshots(self):
        with self.lock:
            return {code:dict(data) for code,data in self.by_code.items()},self.connected,self.error

    def subscription_payload(self, channel, code, action="1"):
        return json.dumps({"header":{"approval_key":self.approval,"custtype":"P",
                           "tr_type":action,"content-type":"utf-8"},
                           "body":{"input":{"tr_id":channel,"tr_key":code}}})

    def update_symbols(self, codes):
        # Serialize membership changes; unsubscribe first to stay within our budget.
        with self.subscription_lock:
            wanted=tuple(dict.fromkeys(codes))
            with self.lock:old=self.codes
            if wanted==old:return
            if not self.connected or not self.ws or not self.approval:
                raise RuntimeError("실시간 구독 연결 준비 중")
            remove=[code for code in old if code not in wanted]
            add=[code for code in wanted if code not in old]
            for action,items in (("2",remove),("1",add)):
                for code in items:
                    for channel in self.channels:
                        self.ws.send(self.subscription_payload(channel,code,action))
                        time.sleep(.15)
            with self.lock:
                self.codes=wanted
                self.code=wanted[0]
                self.by_code={code:self.by_code.get(code,{}) for code in wanted}
                self.data=dict(self.by_code.get(self.code,{}))

    def diagnostics(self):
        with self.lock:
            return {"connected":self.connected,"approved_channels":sorted(self.acknowledged),
                    "contract_code":self.code or "","symbols":list(self.codes),"reconnect_count":self.reconnect_count,"error":self.error,
                    "close_code":self.close_code,"subscription_code":self.subscription_code}

    def stop(self):
        self.stop_event.set()
        if self.ws is not None:
            self.ws.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=12)
        with self.lock:
            self.connected=False
            self.acknowledged.clear()

    def start(self, code, appkey, appsecret, market="UN"):
        owner_lock,owners=websocket_owners()
        key_hash=hashlib.sha256(str(appkey).encode()).hexdigest()
        with owner_lock:
            previous=owners.get(key_hash)
            if previous is not None and previous is not self:
                previous.stop()
                if previous.thread and previous.thread.is_alive():
                    self.error="기존 실시간 연결 종료 대기 중"
                    return
            owners[key_hash]=self
            self._start_owned(code,appkey,appsecret,market)

    def _start_owned(self, code, appkey, appsecret, market="UN"):
        inputs=code if isinstance(code,(list,tuple,set)) else [code]
        codes=tuple(dict.fromkeys(str(c).zfill(6) for c in inputs))
        if not codes or len(codes)>(1 if market=="NIGHT_FUTURE" else 10):
            self.error="실시간 감시는 국내 최대 10종목 · 야간선물 1종목"
            return
        if market!="NIGHT_FUTURE" and not all(len(c)==6 and c.isascii() and c.isdigit() for c in codes):
            self.error="유효하지 않은 종목코드"
            return
        if self.thread and self.thread.is_alive() and self.market==market:
            if self.codes==codes:return
            try:
                self.update_symbols(codes)
            except Exception as exc:
                self.error="구독 변경 실패: "+type(exc).__name__
            return
        code=codes[0]
        self.stop()
        if self.thread and self.thread.is_alive():
            self.error="이전 연결 종료 대기 중"
            return
        self.stop_event=threading.Event()
        self.code=code
        self.codes=codes
        self.by_code={c:{} for c in codes}
        self.approval=None
        self.market=market
        self.reconnect_count=0
        self.close_code=None
        self.subscription_code=""
        self.data={}
        self.acknowledged=set()
        self.error=""
        self.thread=threading.Thread(
            target=self._run,args=(code,appkey,appsecret,market),daemon=True)
        self.thread.start()

    def _run(self, code, appkey, appsecret, market="UN"):
        try:
            import websocket
        except Exception:
            self.error="websocket-client 패키지가 없습니다."
            return
        try:
            rr=requests.post(
                "https://openapi.koreainvestment.com:9443/oauth2/Approval",
                headers={"content-type":"application/json"},
                data=json.dumps({"grant_type":"client_credentials",
                                 "appkey":appkey,"secretkey":appsecret}),
                timeout=10)
            rr.raise_for_status()
            approval=rr.json()["approval_key"]
        except Exception as e:
            self.error=f"WebSocket 접속키 발급 실패: {type(e).__name__}"
            return

        self.approval=approval
        if not self.codes:self.codes=(code,)
        if not self.by_code:self.by_code={c:{} for c in self.codes}

        channels={"UN":("H0UNCNT0","H0UNASP0","H0UNPGM0"),"NX":("H0NXCNT0","H0NXASP0","H0NXPGM0"),"J":("H0STCNT0","H0STASP0","H0STPGM0"),"NIGHT_FUTURE":("H0MFCNT0",)}.get(market)
        if channels is None:
            self.error="지원하지 않는 시장 코드"
            return

        self.channels=channels

        def on_open(ws):
            with self.lock:
                self.connected=True
                self.acknowledged.clear()
                self.error=""
            with self.subscription_lock:
                for symbol in self.codes:
                    for channel in channels:
                        ws.send(self.subscription_payload(channel,symbol))
                        time.sleep(.15)

        def on_error(ws, err):
            with self.lock:
                self.error=f"WebSocket 오류: {type(err).__name__}"
                self.connected=False

        def on_close(ws, *args):
            with self.lock:
                self.connected=False
                self.acknowledged.clear()
                self.close_code=args[0] if args and isinstance(args[0],int) else None

        def on_message(ws, message):
            if self.stop_event.is_set():
                try: ws.close()
                except Exception: pass
                return
            try:
                if not message:
                    return
                if message[0] == "0":
                    for upd in (parse_futures_packet(message,code) if market=="NIGHT_FUTURE" else parse_market_packet(message)):
                        with self.lock:
                            symbol=upd["코드"]
                            if symbol in self.codes:
                                self.by_code.setdefault(symbol,{}).update(upd)
                                if symbol==self.code:self.data=dict(self.by_code[symbol])
                else:
                    # KIS sends JSON subscription acknowledgements / ping messages.
                    try:
                        obj=json.loads(message)
                        if obj.get("header",{}).get("tr_id")=="PINGPONG":
                            ws.send(message,opcode=websocket.ABNF.OPCODE_PONG)
                        elif obj.get("body",{}).get("rt_cd")=="0":
                            with self.lock:self.acknowledged.add(obj.get("header",{}).get("tr_id"))
                        elif "rt_cd" in obj.get("body",{}):
                            # Expose only a bounded API code, never raw messages or credentials.
                            raw_code=str(obj.get("body",{}).get("msg_cd", ""))
                            safe_code=raw_code if 1<=len(raw_code)<=32 and all(c.isascii() and (c.isalnum() or c in "_-") for c in raw_code) else "UNKNOWN"
                            with self.lock:
                                self.subscription_code=safe_code
                                self.error=f"KIS 구독 거절: {safe_code}"
                            if safe_code=="OPSP8996":
                                with self.lock:self.error="OPSP8996 · 같은 App Key의 기존 연결 사용 중 · 자동 재시도 중지"
                                self.stop_event.set()
                                ws.close()
                    except Exception:
                        pass
            except Exception as e:
                self.error=f"실시간 데이터 처리: {type(e).__name__}"

        try:
            ws=websocket.WebSocketApp(
                "ws://ops.koreainvestment.com:21000",
                on_open=on_open,on_message=on_message,
                on_error=on_error,on_close=on_close)
            self.ws=ws
            delay=1
            failures=0
            while not self.stop_event.is_set():
                started=time.monotonic()
                ws.run_forever(ping_interval=None)
                with self.lock:self.connected=False
                if self.stop_event.is_set():break
                # A stable connection resets the consecutive failure budget.
                failures=1 if time.monotonic()-started>=60 else failures+1
                if failures>=5:
                    with self.lock:self.error="연결 5회 연속 실패 · 자동 재접속 중지 · 다시 시작 필요"
                    break
                if self.stop_event.wait(delay):break
                with self.lock:self.reconnect_count+=1
                delay=min(delay*2,30)
        except Exception as e:
            self.error=f"WebSocket 연결: {type(e).__name__}"
            self.connected=False

@st.cache_resource(show_spinner=False)
def _cached_live_tape(session_id, protocol_version="multi-v1"):
    return KISLiveTape()

def live_tape():
    import uuid
    sid=st.session_state.setdefault("tape_session_id",str(uuid.uuid4()))
    return _cached_live_tape(sid,"multi-v1")


def add_trade_levels(a, d):
    close=float(a["종가"])
    av=float(atr(d).iloc[-1]) if len(d)>=15 and not pd.isna(atr(d).iloc[-1]) else close*0.025
    support=float(a["지지"])
    entry_low=max(support, close-0.45*av)
    entry_high=close+0.15*av
    stop=max(0, min(support*0.985, entry_low-1.15*av))
    risk=max(entry_high-stop, av*0.7)
    digits=0 if str(a.get("코드","")).isdigit() else 2
    a["매수하단"]=round(entry_low,digits)
    a["매수상단"]=round(entry_high,digits)
    a["손절가"]=round(stop,digits)
    a["1차목표"]=round(entry_high+1.5*risk,digits)
    a["2차목표"]=round(entry_high+2.5*risk,digits)
    return a


def analyze(t, nm, d):
    if len(d) < 65: return None
    d=d.copy()
    for p in [5,10,20,60]:
        d[f"MA{p}"]=d["종가"].rolling(p).mean()
    d["VOL20"]=d["거래량"].rolling(20).mean()
    d["VAL20"]=d["거래대금"].rolling(20).mean()
    d["RSI"]=rsi(d["종가"])
    d["OSC"]=macd_osc(d["종가"])
    d["ATR"]=atr(d)
    d["HH20"]=d["고가"].rolling(20).max().shift(1)

    x,p=d.iloc[-1],d.iloc[-2]
    close=float(x["종가"]); op=float(x["시가"]); hi=float(x["고가"]); lo=float(x["저가"])
    ma5,ma10,ma20,ma60=[float(x[f"MA{k}"]) for k in [5,10,20,60]]
    vr=float(x["거래량"])/float(x["VOL20"]) if x["VOL20"] else np.nan
    tr=float(x["거래대금"])/float(x["VAL20"]) if x["VAL20"] else np.nan
    rv=float(x["RSI"]); osc=float(x["OSC"]); prevosc=float(p["OSC"])
    dist=(close/ma20-1)*100
    chg=(close/float(p["종가"])-1)*100
    hh=float(x["HH20"]) if not pd.isna(x["HH20"]) else np.nan

    trend=close>ma20>ma60
    align=close>ma5>ma10>ma20
    reclaim=lo<=ma20*1.01 and close>=ma20
    breakout=not np.isnan(hh) and close>hh
    vs=not np.isnan(vr) and vr>=1.5
    ts=not np.isnan(tr) and tr>=1.4
    mu=osc>prevosc
    rok=48<=rv<=72

    score=0; why=[]
    for cond,pts,txt in [
        (trend,18,"20>60 상승추세"),(align,14,"정배열"),(reclaim,16,"20일선 눌림회복"),
        (breakout,18,"20일 고점돌파"),(vs,12,"거래량 급증"),(ts,8,"거래대금 증가"),
        (mu,8,"MACD 개선"),(rok,4,"RSI 양호"),(close>op,2,"양봉")
    ]:
        if cond: score+=pts; why.append(txt)
    if rv>=80: score-=12; why.append("RSI 과열")
    if dist>=12: score-=10; why.append("20일선 과이격")
    if chg>=15: score-=6; why.append("추격위험")

    setup=[]
    if reclaim and trend: setup.append("눌림")
    if breakout and vs: setup.append("돌파")
    if align and vs and chg>0: setup.append("모멘텀")
    av=float(x["ATR"]) if not pd.isna(x["ATR"]) else np.nan
    stop=min(ma20*.985, close-1.5*av) if not np.isnan(av) else ma20*.985

    result = {
        "코드":t,"종목":nm,"점수":int(max(0,min(100,round(score)))),
        "셋업":"/".join(setup) if setup else "관찰","종가":int(close) if str(t).isdigit() else round(close,2),"등락%":round(chg,2),
        "20일이격%":round(dist,2),"거래량x":round(vr,2) if not np.isnan(vr) else np.nan,
        "거래대금x":round(tr,2) if not np.isnan(tr) else np.nan,"RSI":round(rv,1),"MACD_OSC":osc,"ATR":av,"MA20":ma20,"거래대금":float(x["거래대금"]),"기술기준일":str(d.index[-1]),
        "손절참고":int(max(stop,0)),"지지":int(ma20),"저항":int(d["고가"].tail(20).max()),
        "체크":" · ".join(why[:6])
    }
    return add_trade_levels(result, d)

def run_scan(markets, per_market, min_value, min_score):
    end=business_day()
    start=end-dt.timedelta(days=180)
    ls=listing()
    if ls.empty:
        raise RuntimeError("FinanceDataReader 종목 목록을 불러오지 못했습니다.")

    # Normalize market column and keep selected markets.
    market_col = "Market" if "Market" in ls.columns else None
    if market_col:
        ls=ls[ls[market_col].astype(str).str.upper().isin(markets)].copy()
    code_col="Code" if "Code" in ls.columns else "Symbol"
    name_col="Name"
    ls[code_col]=ls[code_col].astype(str).str.zfill(6)

    # Prefer liquid/large names if listing exposes Amount/Marcap; otherwise preserve listing order.
    sort_col=None
    for c in ["Amount","Marcap","MarketCap"]:
        if c in ls.columns:
            sort_col=c; break
    if sort_col:
        ls=ls.sort_values(sort_col,ascending=False)

    universe=[]
    for m in markets:
        part=ls[ls[market_col].astype(str).str.upper()==m] if market_col else ls
        for _,r in part.head(per_market).iterrows():
            universe.append((m,r[code_col],r[name_col]))
    if not universe:
        raise RuntimeError("선택한 시장의 종목 목록이 비어 있습니다.")

    st.caption(f"📅 기술데이터 기준: {end:%Y-%m-%d} · 장중 갱신: {'KIS 현재가' if kis_configured() else '미연결(일봉 모드)'}")
    bar=st.progress(0,"빠른 병렬 스캔 중...")
    out=[]
    def one(item):
        m,t,nm=item
        d=prices(t,start.isoformat(),end.isoformat())
        if len(d)<65: return None
        latest_value=float(d["거래대금"].iloc[-1]) if "거래대금" in d else 0
        a=analyze(t,nm,d)
        if a:
            a["시장"]=m
            return a
        return None
    workers=min(16,max(4,len(universe)//40))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs=[ex.submit(one,item) for item in universe]
        done=0
        for f in as_completed(futs):
            done+=1
            try:
                a=f.result()
                if a: out.append(a)
            except Exception:
                pass
            if done==1 or done%5==0 or done==len(universe):
                bar.progress(done/max(1,len(universe)),f"{done}/{len(universe)} 빠른 스캔")
    bar.empty()

    # Optional KIS fresh quote refresh for the strongest candidates only.
    if out and kis_configured():
        prelim=sorted(out,key=lambda x:x["점수"],reverse=True)[:30]
        with ThreadPoolExecutor(max_workers=5) as ex:
            qf={ex.submit(kis_quote,a["코드"]):a for a in prelim}
            for f in as_completed(qf):
                a=qf[f]
                q=f.result()
                if q:
                    a.update(q)
                    if q["현재가"]>0:
                        a["종가"]=int(q["현재가"])
                        a["등락%"]=round(q["장중등락%"],2)

    if not out: return pd.DataFrame()

    # ULTIMATE integration: live-rescore the actual scan output, not just helper functions.
    frame=pd.DataFrame(out)
    if kis_configured():
        for idx in frame.sort_values("점수",ascending=False).head(10).index:
            inv=kis_investor(frame.at[idx,"코드"])
            if not inv.empty:
                latest=inv.sort_values("일자",ascending=False).iloc[0]
                frame.at[idx,"수급기준일"]=str(latest["일자"])
                for key in ["외국인","기관","개인"]:frame.at[idx,key]=latest[key]
    # Map original scanner fields into the normalized ULTIMATE scoring schema.
    frame["현재가"]=pd.to_numeric(frame.get("현재가",frame["종가"]),errors="coerce").fillna(frame["종가"])
    frame["거래대금"]=pd.to_numeric(frame["장중거래대금"],errors="coerce").fillna(frame["거래대금"]) if "장중거래대금" in frame.columns else frame["거래대금"]
    frame["거래량비"]=pd.to_numeric(frame["거래량x"],errors="coerce").fillna(1) if "거래량x" in frame.columns else pd.Series(1.0,index=frame.index)
    frame["20일이격"]=100+(pd.to_numeric(frame["20일이격%"],errors="coerce").fillna(0) if "20일이격%" in frame.columns else pd.Series(0.0,index=frame.index))
    # Preserve the actual MACD oscillator produced by analyze().
    frame["등락률"]=frame["등락%"]
    frame=enrich_scan_dataframe(frame)

    # Existing KIS investor endpoint is confirmed/end-of-day, so never label it as live.
    # Live program/foreign flow can be integrated later only when a verified live endpoint is configured.
    frame["분석무결성"]=[integrity_status(r.to_dict()) for _,r in frame.iterrows()]
    frame["실시간단타점수"]=[
        integrity_adjusted_score(r.to_dict(),"NORMAL",row_live_health(r))
        for _,r in frame.iterrows()
    ]
    # Use the ULTIMATE execution levels as the current decision-support levels.
    frame["매수하단"]=frame["매수관심하단"]
    frame["매수상단"]=frame["매수관심상단"]
    frame["손절가"]=frame["손절기준"]
    frame["1차목표"]=frame["1차익절"]
    frame["2차목표"]=frame["2차익절"]
    # Official evidence reattaches to a newly computed base on every rerank.
    frame=attach_all_evidence(frame)
    st.session_state.watch_candidates=frame
    return frame[(frame["점수"]>=min_score)&(frame["거래대금"]>=min_value)].copy()


US_SYMBOLS={"MSFT":"NAS","AMD":"NAS","NVDA":"NAS","MU":"NAS","IONQ":"NYS","RKLB":"NAS","VRT":"NYS","VOO":"AMS","QQQM":"NAS","AAPL":"NAS","AMZN":"NAS"}

def kis_us_quote(symbol,exchange):
    if not kis_configured():return None
    try:
        key=secret_value("KIS_APP_KEY");secret=secret_value("KIS_APP_SECRET")
        response=kis_get("https://openapi.koreainvestment.com:9443/uapi/overseas-price/v1/quotations/price",
                         {"appkey":key,"appsecret":secret,"tr_id":"HHDFS00000300","custtype":"P"},
                         {"AUTH":"","EXCD":exchange,"SYMB":symbol},key,secret)
        payload=response.json()
        if payload.get("rt_cd")!="0":return None
        out=payload.get("output",{});price=_safe_num(out.get("last"))
        if price<=0:return None
        return {"현재가":price,"장중등락%":_safe_num(out.get("rate")),"장중거래량":_safe_num(out.get("tvol")),
                "quote_received_utc":pd.Timestamp.now(tz="UTC").isoformat(),"시세출처":"KIS 해외 REST · 거래소 시세 지연 여부 별도 확인"}
    except Exception:return None

def run_us_scan(symbols,min_score):
    out=[];end=market_date("America/New_York");start=end-dt.timedelta(days=240)
    for symbol in symbols:
        bars=prices(symbol,start.isoformat(),end.isoformat())
        if len(bars)<65:continue
        row=analyze(symbol,symbol,bars)
        if not row or row["점수"]<min_score:continue
        row.update({"시장":"US","currency":"USD","20일이격":100+row["20일이격%"],"거래량비":row["거래량x"],"등락률":row["등락%"]})
        quote=kis_us_quote(symbol,US_SYMBOLS.get(symbol,"NAS"))
        if quote:row.update(quote)
        out.append(row)
    if not out:return pd.DataFrame()
    frame=enrich_scan_dataframe(pd.DataFrame(out))
    frame["장기점수설명"]="장기 기술점수 · 기업가치/재무평가 별도"
    frame["상태"]="대기 · 미국 시세 지연/수급 검증 필요"
    for label,source in [("매수하단","매수관심하단"),("매수상단","매수관심상단"),("손절가","손절기준"),("1차목표","1차익절"),("2차목표","2차익절")]:frame[label]=frame[source]
    return frame.sort_values(["단타점수","스윙점수"],ascending=False)

def parse_futures_master(text):
    contracts=[]
    for line in text.splitlines():
        f=[x.strip() for x in line.split("|")]
        if len(f)!=9 or f[0]!="1" or f[7]!="2001" or f[8]!="KOSPI200":continue
        if len(f[1])!=6 or not f[1].isalnum():continue
        if not f[6].isdigit():continue
        contracts.append({"code":f[1],"name":f[3],"rank":int(f[6])})
    if not contracts:raise ValueError("KOSPI200 futures master empty")
    return min(contracts,key=lambda x:x["rank"])

@st.cache_data(ttl=3600,show_spinner=False)
def current_kospi_future():
    import io,zipfile
    r=requests.get("https://new.real.download.dws.co.kr/common/master/fo_idx_code_mts.mst.zip",timeout=12)
    r.raise_for_status()
    if len(r.content)>8_000_000:raise ValueError("oversized master")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        members=[x for x in z.infolist() if x.filename.endswith("fo_idx_code_mts.mst")]
        if len(members)!=1 or members[0].file_size>20_000_000:raise ValueError("invalid master archive")
        return parse_futures_master(z.read(members[0]).decode("cp949"))

@st.cache_data(ttl=20,show_spinner=False)
def domestic_future_snapshot():
    label="국내선물"
    try:
        contract=current_kospi_future()
        if not kis_configured():return {"지표":label,"상태":"KIS 키 미설정"}
        payload=kis_chart_response(contract["code"],"/uapi/domestic-futureoption/v1/quotations/inquire-price","FHMIF10000000",
            {"FID_COND_MRKT_DIV_CODE":"F","FID_INPUT_ISCD":contract["code"]})
        o=payload.get("output1",{})
        price=float(o.get("futs_prpr") or 0);change=float(o.get("futs_prdy_ctrt"))
        if not np.isfinite(price) or price<=0 or not np.isfinite(change):raise ValueError("invalid futures response")
        return {"지표":label,"최근값":price,"전일대비%":change,"기준일":contract["name"]+" · "+contract["code"],
                "수신시각":pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S KST"),
                "상태":"KIS 선물 REST 응답 · 거래시각 미확인"}
    except Exception as exc:return {"지표":label,"상태":"선물 조회 실패 · "+type(exc).__name__}

@st.cache_resource(show_spinner=False)
def night_future_tape(session_id):
    return KISLiveTape()

def night_future_status(data,diagnostics):
    if diagnostics.get("error"):return diagnostics["error"]
    if not diagnostics.get("connected"):return "소켓 미연결 · 실시간 미검증"
    approved="H0MFCNT0" in diagnostics.get("approved_channels",[])
    if not approved:return "소켓 연결 · 구독 승인 대기 · 실제 체결 미검증"
    if not data:return "구독 승인 · 실제 체결 대기"
    return "구독 승인 · 야간 체결 수신 · 거래일 미확인" if timestamp_fresh(data.get("수신시각")) else "구독 승인 · 과거 체결 · 최신 아님"

def night_future_snapshot():
    tape=night_future_tape(st.session_state.setdefault("tape_session_id",str(uuid.uuid4())))
    data,_,_=tape.snapshot()
    diagnostics=tape.diagnostics()
    row={"지표":"국내 야간선물","상태":night_future_status(data,diagnostics),
         "계약코드":diagnostics["contract_code"],"구독승인":"H0MFCNT0" in diagnostics["approved_channels"],
         "재연결횟수":diagnostics["reconnect_count"],
         "구독응답코드":diagnostics.get("subscription_code") or "없음",
         "연결종료코드":diagnostics.get("close_code") or "없음"}
    if data:
        row.update({"최근값":data["최근값"],"전일대비%":data["전일대비%"],"기준일":"체결시간 "+data["체결시간"]+" · 거래일 미확인",
                    "수신시각":data["수신시각"]})
    return row

def parse_index_quote(payload,label):
    if str(payload.get("rt_cd"))!="0":raise ValueError("index API response failed")
    o=payload.get("output",{})
    value=float(o.get("bstp_nmix_prpr") or 0)
    change=float(o.get("bstp_nmix_prdy_ctrt"))
    if not np.isfinite(value) or value<=0 or not np.isfinite(change):raise ValueError("invalid index quote")
    return {"지표":label,"최근값":value,"전일대비%":change,
            "기준일":"공급 기준시각 미확인","수신시각":pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S KST"),
            "상태":"KIS 현재지수 응답 · 거래시각 미확인"}

@st.cache_data(ttl=20,show_spinner=False)
def kis_index_snapshot():
    if not kis_configured():return []
    rows=[]
    for label,code in (("KOSPI","0001"),("KOSDAQ","1001"),("KOSPI200","2001")):
        try:
            payload=kis_chart_response(code,"/uapi/domestic-stock/v1/quotations/inquire-index-price","FHPUP02100000",
                                       {"FID_COND_MRKT_DIV_CODE":"U","FID_INPUT_ISCD":code})
            rows.append(parse_index_quote(payload,label))
        except Exception as exc:
            rows.append({"지표":label,"상태":"KIS 미수신 · "+type(exc).__name__})
    return rows

@st.cache_data(ttl=300,show_spinner=False)
def delayed_macro_snapshot():
    registry={"KOSPI":"KS11","KOSDAQ":"KQ11","KOSPI200":"KS200","NASDAQ":"IXIC","S&P500":"S&P500",
              "SOX":"YAHOO:^SOX","달러/원":"USD/KRW","브렌트유 선물":"BZ=F","미국10년금리":"US10YT"}
    rows=[];end=market_date();start=end-dt.timedelta(days=30)
    for label,symbol in registry.items():
        try:
            data=fdr.DataReader(symbol,start.isoformat(),end.isoformat())
            series=data["Close"] if "Close" in data else data.iloc[:,0]
            series=pd.to_numeric(series,errors="coerce").dropna()
            if len(series)<2:raise ValueError("insufficient observations")
            rows.append({"지표":label,"최근값":float(series.iloc[-1]),"전일대비%":round((series.iloc[-1]/series.iloc[-2]-1)*100,2),
                         "기준일":str(series.index[-1]),"상태":"과거값 · 최신 아님" if (pd.Timestamp.now(tz="UTC").date()-pd.Timestamp(series.index[-1]).date()).days>5 else "일별·지연"})
        except Exception as exc:rows.append({"지표":label,"상태":"미수신 · "+type(exc).__name__})
    rows.extend([{"지표":"국내선물","상태":"KIS 선물 종목·계약코드 연결 필요"},{"지표":"국내 야간선물","상태":"야간시장 공급자 연결 필요"}])
    rows.extend([{"지표":label,"상태":"실시간 공급자·현재 계약 연결 필요"} for label in ("NASDAQ100 선물","S&P500 선물","WTI 선물")])
    return pd.DataFrame(rows)

def macro_snapshot():
    daily=delayed_macro_snapshot()
    live=kis_index_snapshot()+[domestic_future_snapshot(),night_future_snapshot()]
    if live:
        labels={r["지표"] for r in live}
        return pd.concat([pd.DataFrame(live),daily[~daily["지표"].isin(labels)]],ignore_index=True)
    return daily

@st.fragment(run_every=20)
def market_sidebar():
    st.subheader("🌎 시장 흐름")
    enabled=st.toggle("시장 지표 표시·자동 갱신",value=False,key="market_panel_enabled")
    st.caption("실시간 연결 검증 전 · 국내지수 KIS는 20초마다 조회. 해외는 일별/지연 · 수신시각과 공급 기준시각은 다릅니다.")
    if not enabled:
        st.caption("코스피·코스닥·나스닥·SOX·유가·금리·환율과 선물 연결 상태")
        return
    if st.button("시장 지표 다시 조회",key="sidebar_macro_refresh"):
        delayed_macro_snapshot.clear()
        kis_index_snapshot.clear()
        domestic_future_snapshot.clear()
    if st.button("야간선물 구독 시작",key="start_night_future"):
        try:
            contract=current_kospi_future()
            tape=night_future_tape(st.session_state.setdefault("tape_session_id",str(uuid.uuid4())))
            tape.start(contract["code"],secret_value("KIS_APP_KEY"),secret_value("KIS_APP_SECRET"),market="NIGHT_FUTURE")
        except Exception as exc:st.error("야간 구독 준비 실패 · "+type(exc).__name__)
    if st.button("야간선물 구독 중지",key="stop_night_future"):
        night_future_tape(st.session_state.setdefault("tape_session_id",str(uuid.uuid4()))).stop()
    frame=macro_snapshot()
    st.session_state.macro=frame
    for _,row in frame.iterrows():
        value=row.get("최근값")
        if pd.notna(value) and np.isfinite(float(value)):
            delta=row.get("전일대비%")
            colored_quote(str(row["지표"]),f"{float(value):,.2f}",delta)
            st.caption(f"{row.get('기준일','')} · {row.get('상태','미확인')}")
            if pd.notna(row.get("수신시각")):st.caption("API 수신: "+str(row["수신시각"]))
        else:
            with st.container(border=True):
                st.markdown("**"+str(row["지표"])+"**")
                st.write("값 없음 · 연결 미완료")
                st.caption(str(row.get("상태","미수신")))
                if row["지표"]=="국내 야간선물":
                    st.caption("계약: "+str(row.get("계약코드",""))+" · 재연결: "+str(row.get("재연결횟수",0)))

with st.sidebar:
    market_sidebar()

st.markdown('<div class="scanner-hero"><svg class="owl-mark" viewBox="0 0 64 64" fill="none" aria-label="부엉이 심볼" role="img"><path d="M10 8l13 9h18l13-9v27c0 15-10 23-22 23S10 50 10 35V8Z" stroke="currentColor" stroke-width="2.5"/><circle cx="23" cy="30" r="10" stroke="currentColor" stroke-width="2"/><circle cx="41" cy="30" r="10" stroke="currentColor" stroke-width="2"/><circle cx="23" cy="30" r="3" fill="currentColor"/><circle cx="41" cy="30" r="3" fill="currentColor"/><path d="m28 40 4 6 4-6M23 51h18" stroke="currentColor" stroke-width="2"/></svg><div><div class="eyebrow">SUNGHO · STOCK SCANNER</div><div class="brand">시장을 읽고, 근거로 판단하다.</div><div class="description">종목 탐색 · 매매 시나리오 · 보유종목 관리</div></div></div>',unsafe_allow_html=True)
st.caption("iPhone/PC 한국주식 단타·스윙 후보 스캐너 · RC15 검증 진행 중 · 빌드 "+build_id())
components.html("""
<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
body{margin:0;font-family:system-ui,-apple-system,sans-serif;color:#f1f5f9;}
.clocks{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.clock{background:#142239;border:1px solid #30415a;border-radius:12px;padding:10px 14px;}
.label{color:#d4bb82;font-size:12px;font-weight:600;}.time{font-size:23px;font-weight:650;font-variant-numeric:tabular-nums;letter-spacing:.04em;margin-top:3px;}.date{font-size:12px;color:#b4c2d4;margin-top:2px;}
@media(max-width:450px){.time{font-size:20px}.clock{padding:9px 10px}.label{font-size:11px}}
</style></head><body><div class="clocks">
<div class="clock"><div class="label">한국 · KST</div><div class="time" id="kr-time">--:--:--</div><div class="date" id="kr-date">시각 확인 중</div></div>
<div class="clock"><div class="label">미국 서부 · PT</div><div class="time" id="us-time">--:--:--</div><div class="date" id="us-date">시각 확인 중</div></div>
</div><script>
const zones=[['kr','Asia/Seoul'],['us','America/Los_Angeles']];
const formats=zones.map(([id,timeZone])=>({id,
 time:new Intl.DateTimeFormat('en-GB',{timeZone,hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}),
 date:new Intl.DateTimeFormat('ko-KR',{timeZone,year:'numeric',month:'2-digit',day:'2-digit',weekday:'short'})}));
const serverUtcMs=__SERVER_UTC_MS__;const startedAt=performance.now();
function tick(){const now=new Date(serverUtcMs+performance.now()-startedAt);for(const f of formats){document.getElementById(f.id+'-time').textContent=f.time.format(now);document.getElementById(f.id+'-date').textContent=f.date.format(now);}}
tick();setInterval(tick,1000);document.addEventListener('visibilitychange',tick);
</script></body></html>
""".replace("__SERVER_UTC_MS__",str(int(pd.Timestamp.now(tz="UTC").timestamp()*1000))),height=100,scrolling=False)
st.caption("시계는 앱 서버 UTC 기준으로 매초 갱신 · 미국 서부 서머타임 자동 적용 · 시세 수신시각과 별도")
st.caption("🟡 KIS 인증정보 설정됨 · 연결 검증 필요" if kis_configured() else "🟡 일봉 모드 — KIS 키 연결 시 장중 현재가 활성화")

if fdr is None:
    st.error("서버에 FinanceDataReader 설치가 필요합니다.")
    st.stop()

with st.expander("⚙️ 스캔 설정", expanded=False):
    markets=st.multiselect("시장",["KOSPI","KOSDAQ"],default=["KOSPI","KOSDAQ"])
    per_market=st.slider("시장별 스캔 수",50,1000,300,50)
    min_value_eok=st.slider("최소 거래대금(억원)",5,500,50,5)
    min_score=st.slider("최소 점수",0,100,45,5)
    include_us=st.toggle("미국 관심종목도 함께 스캔",value=True)
    us_symbols=st.multiselect("미국 스캔 대상",list(US_SYMBOLS),default=list(US_SYMBOLS))
    auto_live=st.toggle("TOP 후보 자동 재평가",value=True)
    refresh_sec=st.select_slider("자동 재평가 주기(초)",options=[10,15,20,30,60],value=20)
    focus_n=st.slider("집중 감시 후보 수",10,50,30,5)
    refresh_batch=st.slider("회당 KIS 갱신 종목 수",3,15,8,1)

if "scan" not in st.session_state: st.session_state.scan=pd.DataFrame()
if "us_scan" not in st.session_state:st.session_state.us_scan=pd.DataFrame()
if "last_live_refresh" not in st.session_state: st.session_state.last_live_refresh=None
if auto_live and not st.session_state.get("watch_candidates",st.session_state.scan).empty and kis_configured():
    try:
        session_now=kr_market_session_safe()
        if session_now!="CLOSED":
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=int(refresh_sec*1000),key="sungho_live_refresh")
            watch=st.session_state.get("watch_candidates",st.session_state.scan)
            watch=refresh_top_candidates_rate_safe(watch,focus_n,refresh_batch)
            st.session_state.watch_candidates=watch
            st.session_state.scan=watch[(watch["점수"]>=min_score)&(watch["거래대금"]>=min_value_eok*100_000_000)].copy()
            st.session_state.last_live_refresh=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    except Exception:
        pass

scan_action,cache_action=st.columns([3,1])
if cache_action.button("캐시 초기화", use_container_width=True):
    st.cache_data.clear()
    st.success("캐시를 비웠습니다. 다음 스캔에서 데이터를 새로 요청합니다.")

if scan_action.button("🚀 지금 스캔",type="primary",use_container_width=True):
    if not markets:
        st.warning("시장을 선택하세요.")
    else:
        status = st.empty()
        status.info("🚀 스캔을 시작합니다. 잠시만 기다려주세요...")
        try:
            result = run_scan(markets, per_market, min_value_eok*100_000_000, min_score)
            st.session_state.scan = result
            if include_us:st.session_state.us_scan=run_us_scan(us_symbols,min_score)
            if not result.empty:
                try:
                    save_scan_snapshot(result, scan_type="manual_market_scan")
                except Exception:
                    pass
            if result.empty:
                status.warning("⚠️ 스캔은 정상 완료됐지만 현재 조건을 통과한 후보가 없습니다. 최소 점수나 거래대금을 낮춰보세요.")
            else:
                status.success(f"✅ 스캔 완료: {len(result)}개 후보")
        except Exception as e:
            status.error(f"❌ 스캔 오류: {type(e).__name__}: {e}")
            st.exception(e)

with st.expander("🌎 지수·선물·환율",expanded=False):
    if st.button("시장 지표 갱신",use_container_width=True):st.session_state.macro=macro_snapshot()
    if "macro" in st.session_state:st.dataframe(st.session_state.macro,hide_index=True,use_container_width=True)
    st.caption("지수·환율·유가 데이터의 기준일을 확인하세요. 미연결 선물은 점수에 사용하지 않습니다.")

with st.expander("🇺🇸 미국 단타·스윙·장기 후보",expanded=False):
    if not st.session_state.us_scan.empty:
        show_candidate_table(st.session_state.us_scan[["종목","단타점수","스윙점수","장기점수","현재가","매수하단","매수상단","손절가","1차목표","2차목표","상태"]] if "현재가" in st.session_state.us_scan else st.session_state.us_scan,"USD")
    else:st.info("스캔 실행 후 미국 관심종목 결과가 표시됩니다.")
    if not st.session_state.us_scan.empty:
        symbol=st.selectbox("미국 차트 종목",st.session_state.us_scan["코드"].astype(str).tolist(),key="us_chart_symbol")
        if st.button("미국 캔들 차트 보기",key="show_us_candle"):
            chart_end=market_date("America/New_York")
            history=prices(symbol,(chart_end-dt.timedelta(days=180)).isoformat(),chart_end.isoformat())
            if history is not None and not history.empty:
                st.plotly_chart(candle_chart(decorate_chart(history),title=symbol+" 일봉 · USD",currency="USD"),use_container_width=True)
                st.caption("일봉/지연 · 가격 단위 USD")
            else:st.warning("미국 일봉을 받지 못했습니다.")
    st.caption("미국 가격 단위 USD · 한국 순위와 별도 비교 · 거래소 시세 지연 여부 미검증")

df=current_entry_view(st.session_state.scan)

if not df.empty:
    if st.session_state.last_live_refresh:
        st.caption(f"🔄 TOP {focus_n} 자동 재평가: {st.session_state.last_live_refresh:%H:%M:%S} KST · {refresh_sec}초 주기")
    elif auto_live:
        st.caption("🟡 자동 재평가 대기 — KIS 연결/첫 스캔 후 활성화")
    monitor_start,monitor_stop=st.columns([3,1])
    if monitor_start.button("TOP 5 + 보유종목 실시간 감시 시작",key="candidate_monitor_start",use_container_width=True):
        st.session_state.candidate_monitor_enabled=True
    if monitor_stop.button("감시 중지",key="candidate_monitor_stop",use_container_width=True):
        st.session_state.candidate_monitor_enabled=False
        live_tape().stop()
    if st.session_state.get("candidate_monitor_enabled"):
        if kis_configured() and websocket_capability():
            held=st.session_state.get("holdings",pd.DataFrame())
            holding_codes=held["코드"].astype(str).tolist() if "코드" in held else []
            monitor_codes=list(dict.fromkeys(holding_codes+df.head(5)["코드"].astype(str).tolist()))[:10]
            live_tape().start(monitor_codes,secret_value("KIS_APP_KEY"),secret_value("KIS_APP_SECRET"),kis_market_code())
            diagnostic=live_tape().diagnostics()
            st.caption("실시간 구독 요청: "+", ".join(diagnostic["symbols"])+" · 소켓 "+str(diagnostic["connected"]))
            if diagnostic["error"]:st.warning(diagnostic["error"])
        else:st.warning("KIS 설정과 WebSocket 패키지 확인 필요")
    st.subheader("현재 진입 조건 통과 후보")
    ready=df[df["상태"]=="진입확인"].head(5)
    if ready.empty:
        st.info("현재 진입 조건을 통과한 후보 없음 · 아래 제한 사유를 확인하세요.")
    else:
        st.markdown(candidate_cards(ready),unsafe_allow_html=True)
        ready_cols=[c for c in ["종목","매수하단","매수상단","손절가","진입검토목표","비용반영손익비"] if c in ready]
        show_candidate_table(ready[ready_cols],"KRW")
        st.warning("데이터·가격 조건 통과 후보입니다. 실제 장중 동작과 성적 검증은 아직 진행 중입니다.")
    st.caption(f"자동 재평가 {'켜짐' if auto_live else '꺼짐'} · {refresh_sec}초마다 최대 {refresh_batch}종목 REST 순환 갱신 · WebSocket은 구독된 최대 10종목 · 앱 연결 유지 필요")
    st.subheader("TOP 5 · 우선 비교")
    st.markdown(candidate_cards(df),unsafe_allow_html=True)
    st.caption("현재 순위의 후보 · 점수는 수익 확률이 아닙니다. 모바일에서는 카드를 좌우로 넘겨 비교하세요.")
    comparison_cols=["종목","매수하단","매수상단","손절가","1차목표","비용반영손익비","상태","진입제한사유"]
    comparison_cols=[c for c in comparison_cols if c in df.columns]
    show_candidate_table(df.head(5)[comparison_cols],"KRW")
    with st.expander(f"전체 후보 {len(df)}개 · 점수와 매매 구간 비교",expanded=False):
        mobile_cols=["종목","실시간단타점수","스윙점수","장기점수","상태","데이터신뢰도","분석무결성","종가","등락%","매수하단","매수상단","돌파확인가","손절가","1차목표","2차목표","거래량x","RSI"]
        show_candidate_table(df[[c for c in mobile_cols if c in df.columns]],"KRW")

    st.subheader("🔎 상세 분석")
    opts={f"{r['종목']} ({r['코드']})":r["코드"] for _,r in df.iterrows()}
    label=st.selectbox("종목 선택",list(opts))
    t=opts[label]; row=df[df["코드"]==t].iloc[0]
    end=business_day()
    h=prices(t,ymd(end-dt.timedelta(days=180)),ymd(end))
    chart_panel,evidence_panel=st.columns([2.2,1])
    with evidence_panel:
        st.markdown("**선택 종목 · 판단 근거**")
        st.write(str(row.get("상태","판단보류")))
        st.caption("데이터: "+str(row.get("데이터신뢰도","일봉/지연")))
        st.write(str(row.get("셋업","-")))
        st.caption(str(row.get("체크","")))
        st.metric("비용 반영 손익비",f"{_safe_num(row.get('비용반영손익비',0)):.2f}")
        st.caption(str(row.get("진입위험사유","")) or "아래 실시간 체결·호가와 매매 시나리오를 확인하세요.")
    with chart_panel:
        if not h.empty:
            h=h.copy()
            h["MA5"]=h["종가"].rolling(5).mean()
            h["MA20"]=h["종가"].rolling(20).mean()
            h["MA60"]=h["종가"].rolling(60).mean()

            h=decorate_chart(h)
            st.caption("캔들: 상승 빨강 · 하락 파랑 | 20일선: 주황 · 5일선: 보라 · 60일선: 초록 · BB: 회색")
            st.plotly_chart(candle_chart(h,title=f"{label} 일봉"),use_container_width=True,
                            config={"displaylogo":False,"scrollZoom":False})
            with st.expander("MACD · RSI 보조지표",expanded=False):
                st.line_chart(h[["MACD","MACD_SIGNAL","MACD_OSC"]].dropna())
                st.line_chart(h[["RSI"]].dropna())

    with st.expander("KIS 당일 분봉",expanded=False):
        if st.button("분봉 갱신",key=f"minute_{t}",use_container_width=True):
            minutes=kis_minute_history(t)
            if not minutes.empty:
                chart=decorate_chart(minutes)
                st.plotly_chart(candle_chart(chart,title=f"{label} 당일 분봉",minute=True),
                                use_container_width=True,config={"displaylogo":False,"scrollZoom":False})
                st.line_chart(chart[["MACD","MACD_SIGNAL","MACD_OSC"]])
                st.caption("당일 최근 최대 30개 분봉 · 20분 이동평균선은 일봉의 20일선과 다릅니다.")
            else:st.warning("분봉 실데이터를 받지 못했습니다.")
    st.subheader("⚡ KIS LIVE")
    q=kis_quote(t)
    ob=kis_orderbook(t)
    if q:
        l1,l2,l3=st.columns(3)
        with l1:colored_quote("KIS 현재가",f"{int(q['현재가']):,}원",q['장중등락%'])
        l2.metric("누적 거래량",f"{int(q['장중거래량']):,}")
        l3.metric("누적 거래대금",f"{int(q['장중거래대금']/100_000_000):,}억")
    if ob:
        o1,o2,o3=st.columns(3)
        o1.metric("매수1",f"{int(ob['매수1']):,}원")
        o2.metric("매도1",f"{int(ob['매도1']):,}원")
        denom=ob["총매도잔량"]+ob["총매수잔량"]
        pressure=(ob["총매수잔량"]/denom*100) if denom else 0
        o3.metric("매수잔량 비중",f"{pressure:.1f}%")
        st.caption(f"총매수잔량 {int(ob['총매수잔량']):,} · 총매도잔량 {int(ob['총매도잔량']):,}")

    inv=kis_investor(t)
    if not inv.empty:
        st.markdown("**외국인·기관 수급 (KIS 제공 확정 데이터)**")
        latest=inv.iloc[0]
        i1,i2,i3=st.columns(3)
        i1.metric("외국인 순매수",f"{int(latest['외국인']):,}주")
        i2.metric("기관 순매수",f"{int(latest['기관']):,}주")
        i3.metric("개인 순매수",f"{int(latest['개인']):,}주")
        st.caption("※ KIS 공식 안내상 종목별 투자자 당일 데이터는 장 종료 후 제공됩니다.")

    estimated=kis_estimated_investor(t)
    if not estimated.empty:
        st.markdown("**외국인·기관 장중 추정 가집계**")
        st.dataframe(estimated,hide_index=True,use_container_width=True,
                     column_config={c:st.column_config.NumberColumn(c,format="%,.0f주") for c in estimated.columns if c!="입력구분"})
        st.caption("KIS 직원 집계 추정치 · 외국인 09:30/11:20/13:20/14:30, 기관 10:00/11:20/13:20/14:30 예정 · 변동 가능. 수신시각: "+estimated.attrs.get("received_utc","미확인"))
        st.caption("응답에 기준일·정확한 집계시각이 없어 당일 실시간 수급으로 확정하거나 진입 점수에 가산하지 않습니다.")
    else:st.caption("외국인·기관 장중 추정가집계: 미수신 · 확정 수급과 별도")

    if websocket_capability():
        tape=live_tape()
        wc1,wc2=st.columns(2)
        if wc1.button("▶ 실시간 체결·호가 시작",use_container_width=True,key=f"ws_start_{t}"):
            if kis_configured():
                symbols=list(dict.fromkeys(list(tape.codes)+[str(t).zfill(6)]))[-10:]
                tape.start(symbols,st.secrets["KIS_APP_KEY"],st.secrets["KIS_APP_SECRET"],kis_market_code())
            else: st.warning("기존 KIS 인증정보를 읽을 수 없습니다.")
            time.sleep(.7)
        if wc2.button("■ 실시간 중지",use_container_width=True,key=f"ws_stop_{t}"):
            st.session_state.candidate_monitor_enabled=False
            tape.stop()
        snap,connected,wserr=tape.snapshot(t)
        st.caption(("🟢 WebSocket 연결 중" if connected else "⚪ WebSocket 대기") +
                   (f" · {wserr}" if wserr else ""))
        if snap and connected:
            w1,w2,w3=st.columns(3)
            w1.metric("실시간 체결가",f"{int(snap.get('현재가',0)):,}원",
                      f"{snap.get('등락%',0):.2f}%")
            w2.metric("체결강도",f"{snap.get('체결강도',0):.1f}")
            w3.metric("실시간 거래량",f"{int(snap.get('누적거래량',0)):,}")
            st.caption(f"체결 {snap.get('체결시간','-')} · 매수1 {int(snap.get('매수1',0)):,} · 매도1 {int(snap.get('매도1',0)):,}")
            if st.button("↻ 실시간 화면 갱신",use_container_width=True,key=f"ws_refresh_{t}"):
                st.rerun()
    else:
        st.info("WebSocket 실시간 스트리밍을 켜려면 requirements.txt에 websocket-client를 추가하세요.")

    a,b=st.columns(2)
    a.metric("종가",f"{int(row['종가']):,}원",f"{row['등락%']}%")
    b.metric("점수",f"{row['점수']}/100",row["셋업"])
    st.subheader("🎯 매매 시나리오")
    c,d=st.columns(2)
    c.metric("매수 구간",f"{int(row['매수하단']):,}~{int(row['매수상단']):,}원")
    d.metric("손절가",f"{int(row['손절가']):,}원")
    with st.expander("💰 포지션 위험 계산",expanded=False):
        account_cash=st.number_input("이 계좌 운용금액(원)",min_value=0,value=100_000_000,step=1_000_000,key=f"cash_{t}")
        risk_pct=st.slider("1회 최대 계좌손실(%)",0.1,2.0,0.5,0.1,key=f"risk_{t}")/100
        max_pos=st.slider("종목 최대 비중(%)",5,50,15,5,key=f"pos_{t}")/100
        plan=position_plan(float(row["매수상단"]),float(row["손절가"]),account_cash,risk_pct,max_pos)
        p1,p2,p3=st.columns(3)
        p1.metric("최대 수량",f"{int(plan['수량']):,}주")
        p2.metric("예상 투입금",f"{int(plan['투입금']):,}원")
        p3.metric("계획 최대손실",f"{int(plan['최대손실']):,}원")
    e,f=st.columns(2)
    e.metric("1차 목표",f"{int(row['1차목표']):,}원")
    f.metric("2차 목표",f"{int(row['2차목표']):,}원")
    g,h2=st.columns(2)
    g.metric("20일 지지",f"{int(row['지지']):,}원")
    h2.metric("RSI",str(row["RSI"]))
    st.info(row["체크"])

    st.download_button("결과 CSV 저장",df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="sungho_scan.csv",mime="text/csv",use_container_width=True)
else:
    st.info("위의 **지금 스캔** 버튼을 누르면 후보 종목이 표시됩니다.")

with st.expander("💼 보유종목 관리", expanded=not st.session_state.get("holdings",pd.DataFrame()).empty):
    st.caption("코드·수량·평단을 입력하세요. 손절·목표가는 차트 분석으로 자동 계산합니다. 최대 5종목 · 원 · 자동 주문 없음 · 비용 차감 전 손익")
    initial=st.session_state.setdefault("holdings",pd.DataFrame(columns=["코드","종목","수량","평단","손절가","익절가"]))
    names,name_status=holding_name_catalog().snapshot(lambda:fdr.StockListing("KRX") if fdr else pd.DataFrame())
    st.session_state.holdings_names=names
    st.caption(name_status)
    st.session_state.setdefault("holdings_draft",initial.copy())
    editor_key="holdings_editor_"+str(st.session_state.get("holdings_editor_revision",0))
    edited=st.data_editor(st.session_state.holdings_draft,num_rows="dynamic",hide_index=True,use_container_width=True,
                         key=editor_key,on_change=holdings_editor_changed,args=(editor_key,),disabled=["손절가","익절가"],
                         column_config={"코드":st.column_config.TextColumn("코드 (6자리)")})
    st.caption("6자리 코드를 입력하고 Enter를 누르면 종목명이 자동 입력됩니다. 조회되지 않으면 직접 입력하세요.")
    save=st.button("보유종목 저장")
    if save:
        try:
            st.session_state.holdings=validate_holdings(edited)
            if st.session_state.get("candidate_monitor_enabled") and not st.session_state.holdings.empty and kis_configured():
                held=st.session_state.holdings["코드"].astype(str).tolist()
                candidates=st.session_state.scan.head(5)["코드"].astype(str).tolist() if "코드" in st.session_state.scan else []
                live_tape().start(list(dict.fromkeys(held+candidates))[:10],secret_value("KIS_APP_KEY"),secret_value("KIS_APP_SECRET"),kis_market_code())
            st.success("현재 세션에 저장했습니다. 재부팅 전 CSV를 내려받으세요.")
        except ValueError as exc:st.error(str(exc))
    refresh_plans=st.button("보유종목 차트 기준 분석 / 갱신",use_container_width=True)
    if (save or refresh_plans) and not st.session_state.holdings.empty:
        plans={}
        with st.spinner("보유종목 일봉·지지·저항·변동성 분석 중"):
            end=business_day()
            for _,position in st.session_state.holdings.iterrows():
                code=str(position["코드"])
                try:
                    history=prices(code,end-dt.timedelta(days=180),end)
                    row=analyze(code,str(position["종목"]),history)
                    plan=holding_chart_plan(row) if row else {}
                    if plan:plans[code]=plan
                    else:st.warning(str(position["종목"])+" · 차트 근거 부족: 자동 기준 대기")
                except Exception:st.warning(str(position["종목"])+" · 차트 조회 실패: 시세 감시 가능, 자동 기준 대기")
        st.session_state.holdings_plans=plans
    st.caption("차트 기준은 저장/갱신 시 고정합니다. 평단 회복을 가정하지 않으며 목표가가 평단보다 낮으면 손실 축소 구간으로 표시합니다.")
    start_holdings,stop_holdings=st.columns([3,1])
    if start_holdings.button("보유종목 실시간 감시 시작",key="holding_monitor_start",use_container_width=True):
        if st.session_state.holdings.empty:st.warning("보유종목을 먼저 저장하세요.")
        elif not kis_configured() or not websocket_capability():st.warning("KIS 설정과 WebSocket 패키지 확인 필요")
        else:
            st.session_state.candidate_monitor_enabled=True
            held=st.session_state.holdings["코드"].astype(str).tolist()
            candidates=st.session_state.scan.head(5)["코드"].astype(str).tolist() if "코드" in st.session_state.scan else []
            live_tape().start(list(dict.fromkeys(held+candidates))[:10],secret_value("KIS_APP_KEY"),secret_value("KIS_APP_SECRET"),kis_market_code())
    if stop_holdings.button("감시 중지",key="holding_monitor_stop",use_container_width=True):
        st.session_state.candidate_monitor_enabled=False
        live_tape().stop()
    st.download_button("보유종목 CSV 백업",st.session_state.holdings.to_csv(index=False).encode("utf-8-sig"),"holdings.csv","text/csv")
    restored=st.file_uploader("보유종목 CSV 복원",type=["csv"],key="holdings_restore")
    if restored is not None and st.button("복원 내용을 입력표로 불러오기"):
        try:
            restored_df=pd.read_csv(restored,dtype={"코드":str})
            st.session_state.holdings=validate_holdings(restored_df)
            st.session_state.holdings_draft=st.session_state.holdings.copy()
            st.session_state.holdings_plans={}
            st.session_state.holdings_editor_revision=st.session_state.get("holdings_editor_revision",0)+1
            st.rerun()
        except Exception:st.error("CSV 형식 확인 필요")
    @st.fragment(run_every="2s")
    def render_holdings_review():
        positions=st.session_state.holdings
        tape_rows,connected,_=live_tape().snapshots()
        rows=[]
        for _,position in positions.iterrows():
            quote=tape_rows.get(str(position["코드"]).zfill(6),{}) if connected else {}
            plan=st.session_state.get("holdings_plans",{}).get(str(position["코드"]),{})
            if plan and not holding_chart_plan({"종가":1,"ATR":.1,"기술기준일":plan.get("기술기준일")}):plan={}
            pos=position.to_dict()
            if not plan:pos.update(손절가=0,익절가=0)
            rows.append(holding_review(pos,quote,plan))
        if rows:
            for reviewed in rows:
                message=str(reviewed["종목"])+" · "+reviewed["의견"]+" · "+reviewed["근거"]
                if reviewed["의견"]=="손절 조건 충족":st.error(message)
                elif reviewed["의견"]=="일부 익절 검토":st.success(message)
                elif reviewed["의견"] in ["판단 보류","손실 축소 검토","수급 약화 점검"]:st.warning(message)
            show_candidate_table(pd.DataFrame(rows),"KRW")
            st.caption("화면 평가 2초 주기 · 30초 이내 실제 체결만 현재가·손익에 반영 · 주문은 직접 확인해야 합니다.")
        st.caption("구독된 보유종목별 실제 체결을 반영합니다. 최대 10종목 동시 감시 · 영구 저장·수급/뉴스 종합 권유 검증은 아직 남아 있습니다.")
    render_holdings_review()

with st.expander("🧪 시스템 진단 / 성적기록", expanded=False):
    st.dataframe(deployment_self_test(),hide_index=True,use_container_width=True)
    ready_df,static_ready=release_readiness()
    st.markdown("**릴리스 준비상태**")
    st.dataframe(ready_df,hide_index=True,use_container_width=True)
    if st.button("WebSocket 검증 연결 시작 (삼성전자)",use_container_width=True):
        if kis_configured():live_tape().start("005930",secret_value("KIS_APP_KEY"),secret_value("KIS_APP_SECRET"),kis_market_code())
        else:st.warning("배포된 앱의 KIS 설정을 읽을 수 없습니다.")
    @st.fragment(run_every="2s")
    def render_verification_connection():
        tape=live_tape()
        tape_data,tape_connected,tape_error=tape.snapshot()
        diagnostics=tape.diagnostics()
        st.caption("WS 소켓: "+str(tape_connected)+" · 수신 체결/호가/프로그램: "+str([bool(tape_data.get(k)) for k in ["trade_received_utc","book_received_utc","program_received_utc"]]))
        st.caption("구독승인: "+str(diagnostics["approved_channels"])+" · 재연결: "+str(diagnostics["reconnect_count"])+
                   " · 구독응답코드: "+str(diagnostics["subscription_code"] or "없음")+
                   " · 연결종료코드: "+str(diagnostics["close_code"] or "없음"))
        if tape_error:st.warning(tape_error)
    render_verification_connection()
    if st.button("🔌 KIS 라이브 최종 테스트",use_container_width=True):
        gate_df,sok,lok,lmsg=live_release_gate()
        st.session_state.live_test_result={"rows":gate_df.to_dict("records"),"passed":bool(sok and lok),"message":lmsg,
            "time":pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S KST"),
            "diagnostics":dict(st.session_state.get("feed_diagnostics",{}))}
    if "live_test_result" in st.session_state:
        result=st.session_state.live_test_result
        st.caption("마지막 라이브 검사: "+result["time"])
        st.dataframe(pd.DataFrame(result["rows"]),hide_index=True,use_container_width=True)
        if result["passed"]:st.success("검증 완료: 모든 필수 증거 확인")
        else:st.warning(result["message"])
        with st.expander("검사 결과 복사·다운로드 (비밀키 제외)"):
            report=result["time"]+"\n"+"\n".join(str(x["항목"])+": "+str(x["상태"]) for x in result["rows"])
            report+="\n연결 진단: "+json.dumps(result["diagnostics"],ensure_ascii=False)
            st.code(report,language=None)
            st.download_button("검사 결과 TXT 다운로드",report,file_name="scanner_live_test.txt",mime="text/plain")
    st.caption("감시 모집단: "+str(len(st.session_state.get("watch_candidates",st.session_state.scan)))+"개 · 이전 후보 밖 종목도 순환 갱신")
    st.caption("공시/뉴스 연결상태: "+str(disclosure_feed_status())+" · DART매핑: "+str(dart_corp_map_status()))
    st.caption("뉴스피드 상태: "+str(news_feed_status())+" · KRX휴장캘린더: "+str(krx_holiday_status()))
    holidayfile=st.file_uploader("KRX 휴장일 CSV (date)",type=["csv"],key="krx_holidays_upload")
    if holidayfile is not None and st.button("KRX 휴장일 적용",use_container_width=True):
        if load_krx_holidays_csv(holidayfile.getvalue()): st.success("KRX 휴장일 캘린더 적용 완료")
        else: st.error("휴장일 CSV 형식을 확인해 주세요.")
    if st.button("공시·뉴스 자동 연결 점검",use_container_width=True):
        st.session_state.feed_diagnostics={}
        if ensure_dart_map():
            dart_recent_disclosures(dart_corp_code("005930"),days=30)
        refresh_news_candidates(pd.DataFrame([{"코드":"005930","종목":"삼성전자"}]),ttl=0)
        st.caption("삼성전자 최근 30일 공시로 연결 검사 · 스캔 점수에는 기존 최근 2일 기준 유지. NO_DISCLOSURES는 정상 응답이지만 기간 내 공시 없음입니다.")
        st.session_state.feed_check_result=dict(st.session_state.get("feed_diagnostics",{}))
        st.session_state.feed_check_time=pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S KST")
    if "feed_check_result" in st.session_state:
        st.caption("마지막 수동 연결 점검: "+st.session_state.get("feed_check_time",""))
        st.write(st.session_state.feed_check_result)
        if st.session_state.feed_check_result.get("DART_MAPPING") in ["ConnectTimeout","ReadTimeout","ConnectionError"]:
            st.warning("DART 네트워크 연결 실패 · 2회 시도 후 중단. 키 유효성은 아직 확인되지 않았습니다. 서버 연결 확인 또는 공식 종목매핑 CSV가 필요합니다.")
    st.caption('뉴스 자동 수집: NAVER_CLIENT_ID·NAVER_CLIENT_SECRET 설정. 새 네이버 클라우드 키는 NAVER_API_PROVIDER="HUB"도 설정하세요. 기존 키는 LEGACY 방식 유지. CSV 피드도 지원합니다.')
    evidence=st.file_uploader("외부 배포 검증 증거 JSON",type=["json"],key="deploy_evidence")
    if evidence is not None and st.button("배포 검증 증거 적용",use_container_width=True):
        try:
            st.session_state.deploy_attestation=json.loads(evidence.getvalue())
            st.success("증거 적용" if deployment_attestation_valid() else "이 빌드와 일치하는 배포 증거가 아닙니다.")
        except Exception:st.warning("검증 증거 JSON 형식을 확인하세요.")
    newsfile=st.file_uploader("신뢰 가능한 뉴스피드 CSV (title 필수)",type=["csv"],key="news_feed")
    if newsfile is not None and st.button("뉴스피드 적용",use_container_width=True):
        if load_news_feed_csv(newsfile.getvalue()):
            st.success("뉴스피드 적용 완료")
        else:
            st.error("뉴스피드 CSV 형식을 확인해 주세요.")
    corpmap=st.file_uploader("DART 종목코드 매핑 CSV (stock_code, corp_code)",type=["csv"],key="dart_map")
    if corpmap is not None and st.button("DART 매핑 적용",use_container_width=True):
        if load_dart_corp_map_csv(corpmap.getvalue()):
            st.success("DART 종목코드 매핑 적용 완료")
        else:
            st.error("매핑 CSV 형식을 확인해 주세요.")
    if st.button("📊 저장된 신호 성적검증",use_container_width=True):
        from performance import evaluate_snapshots
        if AUDIT_FILE.exists():
            history=pd.read_csv(AUDIT_FILE,dtype={"code":str})
            histories={}
            for code in history["code"].dropna().unique()[:50]:
                signals=history[history["code"]==code]
                begin=pd.to_datetime(signals["scan_time_utc"],utc=True).min().date()
                histories[str(code).zfill(6)]=prices(str(code).zfill(6),begin.isoformat(),market_date().isoformat())
            evaluated=evaluate_snapshots(history,histories)
            evaluated["signal_day"]=pd.to_datetime(evaluated["scan_time_utc"],utc=True).dt.tz_convert("Asia/Seoul").dt.date.astype(str)
            evaluated=evaluated.drop_duplicates(["code","signal_day"],keep="first")
            summary=audit_summary(evaluated)
            st.session_state.performance_verified=(len(evaluated.get("d5_ret",pd.Series(dtype=float)).dropna())>=30)
            st.session_state.performance_verified_build=build_id()
            st.dataframe(summary,use_container_width=True)
            st.download_button("검증 성적 CSV",evaluated.to_csv(index=False).encode("utf-8-sig"),file_name="evaluated_signals.csv")
            st.caption("신호 다음 거래일부터 평가 · 비용 20bp · 같은 일봉에서 손절/목표 모두 도달하면 손절 우선. 일봉 근사이며 체결 수익이 아닙니다.")
        else:
            st.warning("검증할 저장 신호가 없습니다.")
    historical_code=st.text_input("과거 검증 종목코드",value="005930",key="historical_code")
    if st.button("과거 일봉 워크포워드 검증",use_container_width=True):
        from performance import walk_forward
        end=business_day();begin=end-dt.timedelta(days=365)
        bars=prices(historical_code,begin.isoformat(),end.isoformat())
        result=walk_forward(bars,historical_code,lambda h:analyze(historical_code,historical_code,h),min_score=min_score) if len(bars)>=65 else pd.DataFrame()
        if not result.empty:
            st.dataframe(audit_summary(result),use_container_width=True)
            st.download_button("과거 검증 CSV",result.to_csv(index=False).encode("utf-8-sig"),file_name="walk_forward.csv")
            st.caption("과거 일봉 기준 · 다음 시가가 매수구간 내일 때 진입 가정 · 겹치는 독립 시나리오 · 실제 체결 성적 아님")
        else:st.warning("충분한 데이터 또는 조건에 맞는 과거 시나리오가 없습니다.")
    audit_bytes=audit_export_bytes()
    if audit_bytes:
        st.download_button("성적기록 백업 다운로드",audit_bytes,file_name="sungho_audit.csv",mime="text/csv",use_container_width=True)
    uploaded=st.file_uploader("성적기록 복원 CSV",type=["csv"],key="audit_restore")
    if uploaded is not None and st.button("성적기록 복원",use_container_width=True):
        if audit_restore_bytes(uploaded.getvalue()):
            st.success("성적기록을 복원했습니다.")

st.caption("ULTIMATE: 기술 스캔 + KIS 현재가/호가 + 확정 투자자 수급 + 선택 종목 WebSocket + 전략별 재점수 + 위험관리 + 감사로그. 자동주문은 안전상 분리되어 있습니다.")
