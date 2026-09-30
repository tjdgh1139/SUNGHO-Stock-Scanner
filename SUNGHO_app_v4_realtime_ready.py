
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import FinanceDataReader as fdr
except Exception:
    fdr = None

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

@st.cache_resource(ttl=21600, show_spinner=False)
def kis_token(appkey, appsecret):
    r=requests.post(
        "https://openapi.koreainvestment.com:9443/oauth2/tokenP",
        json={"grant_type":"client_credentials","appkey":appkey,"appsecret":appsecret},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]

def kis_quote(code):
    if not kis_configured():
        return None
    try:
        appkey=st.secrets["KIS_APP_KEY"]
        appsecret=st.secrets["KIS_APP_SECRET"]
        token=kis_token(appkey,appsecret)
        headers={
            "authorization":f"Bearer {token}", "appkey":appkey, "appsecret":appsecret,
            "tr_id":"FHKST01010100", "custtype":"P"
        }
        params={"FID_COND_MRKT_DIV_CODE":"J","FID_INPUT_ISCD":str(code).zfill(6)}
        r=requests.get(
            "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=headers, params=params, timeout=8,
        )
        r.raise_for_status(); o=r.json().get("output",{})
        px=float(o.get("stck_prpr") or 0)
        vol=float(o.get("acml_vol") or 0)
        val=float(o.get("acml_tr_pbmn") or 0)
        chg=float(o.get("prdy_ctrt") or 0)
        return {"현재가":px,"장중등락%":chg,"장중거래량":vol,"장중거래대금":val}
    except Exception:
        return None

def add_trade_levels(a, d):
    close=float(a["종가"])
    av=float(atr(d).iloc[-1]) if len(d)>=15 and not pd.isna(atr(d).iloc[-1]) else close*0.025
    support=float(a["지지"])
    entry_low=max(support, close-0.45*av)
    entry_high=close+0.15*av
    stop=max(0, min(support*0.985, entry_low-1.15*av))
    risk=max(entry_high-stop, av*0.7)
    a["매수하단"]=int(round(entry_low))
    a["매수상단"]=int(round(entry_high))
    a["손절가"]=int(round(stop))
    a["1차목표"]=int(round(entry_high+1.5*risk))
    a["2차목표"]=int(round(entry_high+2.5*risk))
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
        "셋업":"/".join(setup) if setup else "관찰","종가":int(close),"등락%":round(chg,2),
        "20일이격%":round(dist,2),"거래량x":round(vr,2) if not np.isnan(vr) else np.nan,
        "거래대금x":round(tr,2) if not np.isnan(tr) else np.nan,"RSI":round(rv,1),
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
        if latest_value < min_value: return None
        a=analyze(t,nm,d)
        if a and a["점수"]>=min_score:
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
    return pd.DataFrame(out).sort_values(["점수","거래대금x","거래량x"],ascending=False)

st.title("📈 SUNGHO Scanner")
st.caption("iPhone용 한국주식 단타·스윙 후보 스캐너 · v4")
now_kst=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
st.caption(f"⏱ 화면 기준시각(KST) {now_kst:%Y-%m-%d %H:%M:%S} · " + ("🟢 KIS 장중 현재가 연결" if kis_configured() else "🟡 일봉 모드 — KIS 키 연결 시 장중 현재가 활성화"))

if fdr is None:
    st.error("서버에 FinanceDataReader 설치가 필요합니다.")
    st.stop()

with st.expander("⚙️ 스캔 설정", expanded=False):
    markets=st.multiselect("시장",["KOSPI","KOSDAQ"],default=["KOSPI","KOSDAQ"])
    per_market=st.slider("시장별 스캔 수",50,1000,300,50)
    min_value_eok=st.slider("최소 거래대금(억원)",5,500,50,5)
    min_score=st.slider("최소 점수",0,100,45,5)

if "scan" not in st.session_state: st.session_state.scan=pd.DataFrame()

if st.button("🔄 데이터 캐시 초기화", use_container_width=True):
    st.cache_data.clear()
    st.success("캐시를 비웠습니다. 다음 스캔에서 데이터를 새로 요청합니다.")

if st.button("🚀 지금 스캔",type="primary",use_container_width=True):
    if not markets:
        st.warning("시장을 선택하세요.")
    else:
        status = st.empty()
        status.info("🚀 스캔을 시작합니다. 잠시만 기다려주세요...")
        try:
            result = run_scan(markets, per_market, min_value_eok*100_000_000, min_score)
            st.session_state.scan = result
            if result.empty:
                status.warning("⚠️ 스캔은 정상 완료됐지만 현재 조건을 통과한 후보가 없습니다. 최소 점수나 거래대금을 낮춰보세요.")
            else:
                status.success(f"✅ 스캔 완료: {len(result)}개 후보")
        except Exception as e:
            status.error(f"❌ 스캔 오류: {type(e).__name__}: {e}")
            st.exception(e)

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
    mobile_cols=["종목","점수","셋업","종가","등락%","매수하단","매수상단","손절가","1차목표","2차목표","거래량x","RSI"]
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
    st.subheader("🎯 매매 시나리오")
    c,d=st.columns(2)
    c.metric("매수 구간",f"{int(row['매수하단']):,}~{int(row['매수상단']):,}원")
    d.metric("손절가",f"{int(row['손절가']):,}원")
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

st.caption("v4: 병렬 스캔 + 30초 캐시 + 매수/손절/목표가. KIS 키가 연결되면 상위 후보의 장중 현재가를 다시 반영합니다. 실시간 수급/호가 전체 스캔은 증권사 WebSocket 연결이 필요합니다.")
