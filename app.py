
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st

try:
    from pykrx import stock
    PYKRX_IMPORT_ERROR = None
except Exception as e:
    stock = None
    PYKRX_IMPORT_ERROR = repr(e)

st.set_page_config(
    page_title="SUNGHO Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 5rem; max-width: 1100px;}
h1 {font-size: 1.65rem !important; margin-bottom: .1rem;}
h2, h3 {font-size: 1.15rem !important;}
div[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 14px;
    padding: 10px;
}
.stButton > button {
    min-height: 48px;
    border-radius: 14px;
    font-weight: 700;
    width: 100%;
}
div[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
@media (max-width: 700px) {
    .block-container {padding-left: .75rem; padding-right: .75rem; padding-top: .6rem;}
    h1 {font-size: 1.45rem !important;}
    div[data-testid="column"] {min-width: 0 !important;}
}
</style>
""", unsafe_allow_html=True)

def business_day(d=None):
    d = d or dt.date.today()
    while d.weekday() >= 5:
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

@st.cache_data(ttl=900, show_spinner=False)
def tickers(market, date):
    try: return stock.get_market_ticker_list(date, market=market)
    except: return []

@st.cache_data(ttl=900, show_spinner=False)
def name(t):
    try: return stock.get_market_ticker_name(t)
    except: return t

@st.cache_data(ttl=900, show_spinner=False)
def prices(t, start, end):
    try: return stock.get_market_ohlcv_by_date(start, end, t).copy()
    except: return pd.DataFrame()

@st.cache_data(ttl=900, show_spinner=False)
def caps(date, market):
    try: return stock.get_market_cap_by_ticker(date, market=market)
    except: return pd.DataFrame()

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

    return {
        "코드":t,"종목":nm,"점수":int(max(0,min(100,round(score)))),
        "셋업":"/".join(setup) if setup else "관찰","종가":int(close),"등락%":round(chg,2),
        "20일이격%":round(dist,2),"거래량x":round(vr,2) if not np.isnan(vr) else np.nan,
        "거래대금x":round(tr,2) if not np.isnan(tr) else np.nan,"RSI":round(rv,1),
        "손절참고":int(max(stop,0)),"지지":int(ma20),"저항":int(d["고가"].tail(20).max()),
        "체크":" · ".join(why[:6])
    }

def run_scan(markets, per_market, min_value, min_score):
    end=business_day(); start=end-dt.timedelta(days=150)
    universe=[]
    for m in markets:
        cp=caps(ymd(end),m); ts=tickers(m,ymd(end))
        if not cp.empty:
            cp=cp.copy(); cp["ticker"]=cp.index
            if "거래대금" in cp:
                cp=cp[cp["거래대금"]>=min_value].sort_values("거래대금",ascending=False)
            allowed=set(ts); ts=[t for t in cp["ticker"].tolist() if t in allowed]
        universe += [(m,t) for t in ts[:per_market]]

    bar=st.progress(0,"종목 스캔 중...")
    out=[]
    for i,(m,t) in enumerate(universe,1):
        d=prices(t,ymd(start),ymd(end))
        a=analyze(t,name(t),d) if len(d)>=65 else None
        if a and a["점수"]>=min_score:
            a["시장"]=m; out.append(a)
        bar.progress(i/max(1,len(universe)),f"{i}/{len(universe)} 스캔")
    bar.empty()
    if not out: return pd.DataFrame()
    return pd.DataFrame(out).sort_values(["점수","거래대금x","거래량x"],ascending=False)

st.title("📈 SUNGHO Scanner")
st.caption("iPhone용 한국주식 단타·스윙 후보 스캐너")

if stock is None:
    st.error("pykrx 로딩 실패: " + str(PYKRX_IMPORT_ERROR))
    st.info("배포 환경에서 pykrx를 불러오지 못했습니다. 아래 오류 내용을 확인하세요.")
    st.stop()

with st.expander("⚙️ 스캔 설정", expanded=False):
    markets=st.multiselect("시장",["KOSPI","KOSDAQ"],default=["KOSPI","KOSDAQ"])
    per_market=st.slider("시장별 스캔 수",50,1000,300,50)
    min_value_eok=st.slider("최소 거래대금(억원)",5,500,50,5)
    min_score=st.slider("최소 점수",0,100,45,5)

if "scan" not in st.session_state: st.session_state.scan=pd.DataFrame()

if st.button("🚀 지금 스캔",type="primary",use_container_width=True):
    if markets:
        st.session_state.scan=run_scan(markets,per_market,min_value_eok*100_000_000,min_score)
    else:
        st.warning("시장을 선택하세요.")

df=st.session_state.scan

if not df.empty:
    top=df.head(10)
    st.subheader("🔥 TOP 10")
    for _,r in top.iterrows():
        with st.container(border=True):
            c1,c2,c3=st.columns([2.1,1,1])
            c1.markdown(f"**{r['종목']}**  \n`{r['코드']}` · {r['셋업']}")
            c2.metric("점수",f"{r['점수']}")
            c3.metric("등락",f"{r['등락%']}%")
            st.caption(f"거래량 {r['거래량x']}x · RSI {r['RSI']} · 20일선 이격 {r['20일이격%']}%")
            st.caption(r["체크"])

    st.subheader("📋 전체 후보")
    mobile_cols=["종목","점수","셋업","종가","등락%","거래량x","RSI"]
    st.dataframe(df[mobile_cols],hide_index=True,use_container_width=True)

    st.subheader("🔎 상세 분석")
    opts={f"{r['종목']} ({r['코드']})":r["코드"] for _,r in df.iterrows()}
    label=st.selectbox("종목 선택",list(opts))
    t=opts[label]; row=df[df["코드"]==t].iloc[0]
    end=business_day()
    h=prices(t,ymd(end-dt.timedelta(days=180)),ymd(end))
    if not h.empty:
        h=h.copy()
        h["MA5"]=h["종가"].rolling(5).mean()
        h["MA20"]=h["종가"].rolling(20).mean()
        h["MA60"]=h["종가"].rolling(60).mean()
        st.line_chart(h[["종가","MA5","MA20","MA60"]].dropna())

    a,b=st.columns(2)
    a.metric("종가",f"{int(row['종가']):,}원",f"{row['등락%']}%")
    b.metric("점수",f"{row['점수']}/100",row["셋업"])
    c,d=st.columns(2)
    c.metric("20일 지지",f"{int(row['지지']):,}원")
    d.metric("손절 참고",f"{int(row['손절참고']):,}원")
    e,f=st.columns(2)
    e.metric("저항",f"{int(row['저항']):,}원")
    f.metric("RSI",str(row["RSI"]))
    st.info(row["체크"])

    st.download_button("결과 CSV 저장",df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="sungho_scan.csv",mime="text/csv",use_container_width=True)
else:
    st.info("위의 **지금 스캔** 버튼을 누르면 후보 종목이 표시됩니다.")

st.caption("후보 압축용 도구입니다. 실제 주문 전 뉴스·공시·수급·호가와 리스크를 별도로 확인하세요.")
