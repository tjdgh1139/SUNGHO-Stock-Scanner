import ast
from pathlib import Path
import datetime as dt
import threading,time,json,csv,uuid,hashlib
from feeds import dart_corporations,naver_news,FeedError
from ws_protocol import parse_market_packet
from scoring import overlay_quote,decorate_chart
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
import pandas as pd
import requests
import streamlit as st
from performance import evaluate_snapshots

# Load definitions without executing the interactive page; real Streamlit AppTest below
# independently checks the complete UI.
tree=ast.parse(Path(__file__).with_name('app.py').read_text())
ns=dict(globals())
ns.update(_DART_CORP_MAP={},_DART_CACHE={},_NEWS_CACHE=[],_KRX_HOLIDAYS=set(),fdr=None)
for node in tree.body:
    if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
        node.decorator_list=[]
        exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),ns)
    elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id.endswith('CATALYST_WORDS') for t in node.targets):
        exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),ns)

def test_indicator_propagation():
    x=np.linspace(1000,1400,90)
    df=pd.DataFrame({'종가':x,'시가':x-1,'고가':x+10,'저가':x-10,'거래량':np.arange(90)+1000,'거래대금':x*(np.arange(90)+1000)})
    r=ns['analyze']('005930','삼성전자',df)
    assert r['MACD_OSC']!=0 and r['ATR']>0 and r['MA20']>0
    z=ns['actionable_levels'](r)
    assert 0<z['손절기준']<z['매수관심하단']<=z['매수관심상단']<z['1차익절']<z['2차익절']

def test_delayed_not_live():
    row={'현재가':1000,'거래대금':1e10,'체결강도':120,'호가불균형':1,'프로그램':5,'점수':100}
    assert ns['data_confidence'](row)=='DAILY/DELAYED'
    assert ns['execution_permission'](row,ns['live_health']())=='신규진입금지'

def test_timezone_and_holiday():
    ns['_KRX_HOLIDAYS'].add('2026-10-05')
    assert ns['kr_market_session_safe'](dt.datetime(2026,10,5,10,tzinfo=dt.timezone(dt.timedelta(hours=9))))=='CLOSED'
    assert ns['kr_market_session'](pd.Timestamp('2026-10-06T01:00:00Z'))=='REGULAR'

def test_news_rejects_unknown_future_and_stale():
    now=pd.Timestamp.now(tz='UTC')
    ns['_NEWS_CACHE']=[{'title':'삼성전자 수주','stock_code':'005930','_ts':ts} for ts in ['',(now+pd.Timedelta(hours=1)).isoformat(),(now-pd.Timedelta(hours=25)).isoformat(),now.isoformat()]]
    assert len(ns['news_for_stock']('005930','삼성전자'))==1

def test_refresh_rotates_full_universe_and_reranks(monkeypatch):
    calls=[]
    from types import SimpleNamespace
    monkeypatch.setitem(ns,'live_tape',lambda:SimpleNamespace(snapshot=lambda:({},False,'')))
    monkeypatch.setitem(ns,'kis_configured',lambda:True)
    monkeypatch.setitem(ns,'kr_market_session_safe',lambda:'REGULAR')
    def quote(code):
        calls.append(code)
        return {'현재가':2000,'장중등락%':2,'장중거래대금':1e9,'quote_received_utc':pd.Timestamp.now(tz='UTC').isoformat()}
    monkeypatch.setitem(ns,'kis_quote',quote)
    st.session_state.live_cursor=0
    df=pd.DataFrame([{'코드':str(i).zfill(6),'종가':1000,'점수':50+i,'거래대금x':1,'RSI':60,'MACD_OSC':2} for i in range(6)])
    for _ in range(3): df=ns['refresh_top_candidates_rate_safe'](df,top_n=2,batch_size=2)
    assert len(set(calls))==6
    assert df['실시간단타점수'].is_monotonic_decreasing

def test_performance_no_same_day_lookahead_stop_first():
    snap=pd.DataFrame([{'code':'005930','scan_time_utc':'2026-09-28T02:00:00Z','price':100,'stop':90,'tp1':120}])
    bars=pd.DataFrame({'시가':[100,100,105,110,115,120],'저가':[1,80,100,105,110,115],'고가':[999,130,115,120,125,130],'종가':[999,105,110,115,120,125]},index=pd.date_range('2026-09-28',periods=6))
    r=evaluate_snapshots(snap,{'005930':bars})
    assert r.iloc[0]['evaluation']=='STOP'
    assert abs(r.iloc[0]['d1_ret']-4.8)<1e-8
    assert abs(r.iloc[0]['exit_ret']+10.2)<1e-8

def test_streamlit_startup_and_gate():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=20).run()
    assert not app.exception
    next(b for b in app.button if b.label=="🔌 KIS 라이브 최종 테스트").click().run()
    assert not app.exception
    assert any('미검증' in w.value for w in app.warning)

def test_batched_websocket_trade_and_program():
    trade=['0']*47;trade[0]='005930';trade[1]='093001';trade[2]='1000';trade[5]='1.5';trade[18]='120';trade[33]='20261006'
    parsed=parse_market_packet('0|H0STCNT0|2|'+'^'.join(trade+trade),'2026-10-06T00:30:01Z')
    assert len(parsed)==2 and parsed[0]['체결강도']==120 and parsed[0]['market_date']=='20261006'
    program=['005930','093001','10','100','20','200','10','100','0','0','0']
    assert parse_market_packet('0|H0STPGM0|1|'+'^'.join(program))[0]['프로그램']==10

def test_websocket_book_fields_and_truncation():
    import pytest
    raw=['0']*63;raw[0]='005930';raw[3]='1001';raw[13]='1000';raw[43]='100';raw[44]='300'
    assert parse_market_packet('0|H0STASP0|1|'+'^'.join(raw))[0]['호가불균형']==.5
    with pytest.raises(ValueError):parse_market_packet('0|H0STCNT0|2|'+'^'.join(['0']*53))

def test_official_dart_map_zip():
    import zipfile
    from io import BytesIO
    out=BytesIO()
    with zipfile.ZipFile(out,'w') as z:z.writestr('CORPCODE.xml','<result><list><stock_code>005930</stock_code><corp_code>00126380</corp_code></list></result>')
    class Response:
        content=out.getvalue()
        def raise_for_status(self):pass
    assert dart_corporations('fake',get=lambda *a,**kw:Response())=={'005930':'00126380'}

def test_naver_news_strict_association_and_dates():
    from email.utils import format_datetime
    from datetime import datetime,timezone,timedelta
    stamp=format_datetime(datetime.now(timezone.utc)-timedelta(minutes=5))
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'items':[{'title':'<b>삼성전자</b> 수주','description':'공급계약','pubDate':stamp,'originallink':'https://example.com/article'},{'title':'다른회사 수주','description':'','pubDate':stamp}]}
    rows=naver_news('삼성전자','005930','fake','fake',get=lambda *a,**kw:Response())
    assert len(rows)==1 and rows[0]['title']=='삼성전자 수주'

def test_overlay_quote_no_mutation_no_backwards_bar():
    history=pd.DataFrame({'종가':[100,110],'시가':[95,105],'고가':[105,115],'저가':[90,100],'거래량':[10,15],'거래대금':[1000,1650]},index=pd.date_range('2026-10-01',periods=2))
    original=history.copy()
    quote={'market_date':'20261002','현재가':112,'장중시가':105,'장중고가':115,'장중저가':102,'장중거래량':20,'장중거래대금':2240}
    revised=overlay_quote(history,quote)
    assert revised.iloc[-1]['종가']==112
    pd.testing.assert_frame_equal(history,original)
    quote['market_date']='20261005'
    assert len(overlay_quote(history,quote))==3
    quote['market_date']='20260901'
    pd.testing.assert_frame_equal(overlay_quote(history,quote),original)

def test_chart_constant_and_rising_rsi():
    n=80
    df=pd.DataFrame({'종가':np.ones(n)*100})
    out=decorate_chart(df)
    assert out['RSI'].iloc[-1]==50 and out['MACD_OSC'].iloc[-1]==0
    df['종가']=np.arange(n)+100
    assert decorate_chart(df)['RSI'].iloc[-1]==100

def test_performance_target_gap_precedes_later_intraday_stop():
    snap=pd.DataFrame([{'code':'005930','scan_time_utc':'2026-09-28T02:00:00Z','price':100,'stop':90,'tp1':120,'d5_ret':999}])
    bars=pd.DataFrame({'시가':[125],'저가':[80],'고가':[130],'종가':[100]},index=pd.to_datetime(['2026-09-29']))
    r=evaluate_snapshots(snap,{'005930':bars})
    assert r.iloc[0]['evaluation']=='TARGET_GAP' and 'd5_ret' not in r

def test_negative_or_future_timestamps_never_live():
    row={'현재가':1000,'quote_received_utc':(pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=1)).isoformat()}
    assert ns['data_confidence'](row)=='DAILY/DELAYED'
    assert ns['live_health'](row['quote_received_utc'])['state']!='LIVE'

def test_evidence_rerank_idempotent(monkeypatch):
    monkeypatch.setitem(ns,'ensure_dart_map',lambda:False)
    monkeypatch.setitem(ns,'refresh_news_candidates',lambda *a:None)
    ns['_NEWS_CACHE']=[]
    row={'코드':'005930','종목':'삼성전자','종가':1000,'현재가':1000,'점수':80,'거래대금x':2,'단타점수':80,'RSI':60,'MACD_OSC':1,'뉴스점수':20,'공시점수':20,'실시간단타점수':99}
    one=ns['attach_all_evidence'](pd.DataFrame([row]));two=ns['attach_all_evidence'](one)
    assert one['실시간단타점수'].iloc[0]==two['실시간단타점수'].iloc[0]
    assert two['뉴스점수'].iloc[0]==0

def test_us_currency_keeps_fractional_trade_levels():
    row={'현재가':7.23,'ATR':.31,'MA20':7.1,'currency':'USD'}
    z=ns['actionable_levels'](row)
    assert z['매수관심하단']!=round(z['매수관심하단'])
    assert 0<z['손절기준']<z['매수관심하단']<=z['매수관심상단']<z['1차익절']

def test_walk_forward_prefix_excludes_future():
    from performance import walk_forward
    bars=pd.DataFrame({'시가':[100.]*70,'고가':[105.]*70,'저가':[95.]*70,'종가':[101.]*70},index=pd.date_range('2026-01-01',periods=70))
    lengths=[]
    def signal(history):
        lengths.append(len(history))
        assert len(history)<len(bars)
        return {'점수':70,'매수하단':99,'매수상단':102,'손절가':90,'1차목표':120}
    result=walk_forward(bars,'005930',signal)
    assert lengths==list(range(65,70)) and len(result)==5

def test_full_streamlit_scan_with_fixture(monkeypatch):
    import FinanceDataReader as fdr
    from streamlit.testing.v1 import AppTest
    def reader(*args,**kwargs):
        x=np.linspace(1000,1200,90)
        return pd.DataFrame({'Open':x-1,'High':x+10,'Low':x-10,'Close':x,'Volume':np.ones(90)*10000000},index=pd.date_range('2026-05-01',periods=90))
    monkeypatch.setattr(fdr,'StockListing',lambda *a,**k:pd.DataFrame({'Code':['005930'],'Name':['삼성전자'],'Market':['KOSPI'],'Amount':[1e12]}))
    monkeypatch.setattr(fdr,'DataReader',reader)
    st.cache_data.clear()
    app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30).run()
    next(t for t in app.toggle if t.label=='미국 관심종목도 함께 스캔').set_value(False)
    next(t for t in app.slider if t.label=='최소 점수').set_value(0)
    next(b for b in app.button if b.label=='🚀 지금 스캔').click().run()
    assert not app.exception
    assert any('스캔 완료' in s.value for s in app.success)
    assert not app.session_state['scan'].empty
    assert app.session_state['scan'].iloc[0]['상태']=='신규진입금지'

def test_kis_token_concurrent_start_issues_one_token(monkeypatch):
    import concurrent.futures
    calls=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'access_token':'test-token','expires_in':3600}
    def post(*a,**kw):
        calls.append(True);time.sleep(.01);return Response()
    monkeypatch.setattr(requests,'post',post)
    monkeypatch.setitem(ns,'_TOKEN_STORE',{})
    monkeypatch.setitem(ns,'_TOKEN_LOCK',threading.RLock())
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        result=list(ex.map(lambda _:ns['kis_token']('fake-key','fake-secret'),range(6)))
    assert len(calls)==1 and result==['test-token']*6
    ns['kis_token']('different-key','fake-secret')
    assert len(calls)==2

def test_kis_get_401_refreshes_once(monkeypatch):
    calls=[];tokens=[]
    class Response:
        def __init__(self,status):self.status_code=status
        def raise_for_status(self):
            if self.status_code>=400:raise requests.HTTPError()
    def token(key,secret,force_refresh=False):
        tokens.append(force_refresh);return 'refreshed' if force_refresh else 'first'
    def get(url,**kwargs):
        calls.append(kwargs['headers']['authorization']);return Response(401 if len(calls)==1 else 200)
    monkeypatch.setitem(ns,'kis_token',token)
    monkeypatch.setitem(ns,'kis_rate_wait',lambda:None)
    monkeypatch.setattr(requests,'get',get)
    assert ns['kis_get']('https://example.com',{}, {},'fake','fake').status_code==200
    assert tokens==[False,True] and calls==['Bearer first','Bearer refreshed']

def test_stop_closes_current_websocket():
    from types import SimpleNamespace
    tape=ns['KISLiveTape']();calls=[]
    tape.ws=SimpleNamespace(close=lambda:calls.append('closed'))
    tape.connected=True;tape.stop()
    assert calls==['closed'] and not tape.connected and tape.stop_event.is_set()

def test_source_freshness_requires_all_live_channels():
    stamp=pd.Timestamp.now(tz='UTC').isoformat()
    row={'quote_received_utc':stamp,'rest_received_utc':stamp,'trade_received_utc':stamp,'book_received_utc':stamp,'program_received_utc':stamp}
    assert ns['row_live_health'](row)['state']=='LIVE'
    row.pop('book_received_utc')
    assert ns['row_live_health'](row)['state']=='DEGRADED'

def test_unified_nxt_book_batch_schema():
    raw=['0']*66;raw[0]='005930';raw[3]='1001';raw[13]='1000';raw[43]='100';raw[44]='200'
    result=parse_market_packet('0|H0UNASP0|2|'+'^'.join(raw+raw))
    assert len(result)==2 and result[0]['quote_market']=='UN' and result[0]['매수1']==1000

def test_kis_daily_page_normalization(monkeypatch):
    calls=[]
    def response(code,path,tr_id,params):
        calls.append(params)
        return {'output2':[{'stck_bsop_date':'20261002','stck_oprc':'1000','stck_hgpr':'1010','stck_lwpr':'990','stck_clpr':'1005','acml_vol':'100','acml_tr_pbmn':'100500'},{'stck_bsop_date':'20261001','stck_oprc':'990','stck_hgpr':'1000','stck_lwpr':'980','stck_clpr':'995','acml_vol':'90','acml_tr_pbmn':'89550'}]}
    monkeypatch.setitem(ns,'kis_chart_response',response)
    monkeypatch.setitem(ns,'kis_market_code',lambda:'UN')
    result=ns['kis_daily_history']('005930','2026-09-01','2026-10-03')
    assert len(result)==2 and result.index.is_monotonic_increasing
    assert result.iloc[-1]['종가']==1005 and calls[0]['FID_ORG_ADJ_PRC']=='0'

def test_cancelled_contract_never_positive_catalyst():
    assert ns['catalyst_text_score']('공급계약 수주 계약 해지')['score']<0
    assert not ns['catalyst_text_score']('SCB 은행 실적')['negative']
    assert not ns['catalyst_text_score']('감사의견 적정')['negative']
