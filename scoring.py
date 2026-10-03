"""Pure technical calculations for quote updates; preserves historical bars."""
import numpy as np
import pandas as pd


def overlay_quote(history,quote):
    if history is None or history.empty:return history
    out=history.copy()
    stamp=pd.to_datetime(quote.get('market_date'),format='%Y%m%d',errors='coerce')
    if pd.isna(stamp):return out
    px=float(quote.get('현재가') or 0)
    if px<=0:return out
    values={'종가':px,'시가':float(quote.get('장중시가') or px),
            '고가':max(px,float(quote.get('장중고가') or px)),
            '저가':min(px,float(quote.get('장중저가') or px)),
            '거래량':float(quote.get('장중거래량') or 0),'거래대금':float(quote.get('장중거래대금') or 0)}
    dates=pd.to_datetime(out.index)
    matches=np.flatnonzero(dates.date==stamp.date())
    if len(matches):
        for k,v in values.items():out.loc[out.index[matches[-1]],k]=v
    elif stamp.date()>dates[-1].date():
        if dates.tz is not None:stamp=stamp.tz_localize(dates.tz)
        out.loc[stamp]=values
    return out.sort_index()


def decorate_chart(history):
    out=history.copy();close=pd.to_numeric(out['종가'],errors='coerce')
    for period in (5,20,60):out[f'MA{period}']=close.rolling(period).mean()
    std=close.rolling(20).std()
    out['BB_UPPER']=out['MA20']+2*std;out['BB_LOWER']=out['MA20']-2*std
    fast=close.ewm(span=12,adjust=False).mean();slow=close.ewm(span=26,adjust=False).mean()
    out['MACD']=fast-slow;out['MACD_SIGNAL']=out['MACD'].ewm(span=9,adjust=False).mean()
    out['MACD_OSC']=out['MACD']-out['MACD_SIGNAL']
    diff=close.diff();up=diff.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    down=(-diff.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    out['RSI']=100-100/(1+up/down.replace(0,np.nan))
    out.loc[(down==0)&(up>0),'RSI']=100;out.loc[(down==0)&(up==0),'RSI']=50
    out['20일이격%']=(close/out['MA20']-1)*100
    return out
