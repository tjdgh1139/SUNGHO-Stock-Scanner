"""Forward signal outcome audit; no future data enters signal construction."""
import pandas as pd
import numpy as np

def evaluate_snapshots(snapshots, histories, cost_bps=20, now=None):
    if not 0<=cost_bps<=1000:raise ValueError('Invalid transaction costs')
    required={'code','scan_time_utc','price','stop','tp1'}
    if not required.issubset(snapshots.columns):raise ValueError('Missing snapshot fields')
    result=snapshots.drop(columns=[c for c in ['d1_ret','d3_ret','d5_ret','exit_ret','evaluation'] if c in snapshots],errors='ignore').copy()
    result['evaluation']='PENDING'
    for idx,row in result.iterrows():
        try:
            entry,stop,target=(float(row[field]) for field in ('price','stop','tp1'))
        except (ValueError,TypeError,OverflowError):
            result.at[idx,'evaluation']='INVALID_SNAPSHOT'
            continue
        if not np.isfinite([entry,stop,target]).all() or not 0<stop<entry<target:
            result.at[idx,'evaluation']='INVALID_SNAPSHOT'
            continue
        is_us=str(row.get('market','')).upper()=='US' or str(row.get('scan_type','')).startswith('us_')
        zone='America/New_York' if is_us else 'Asia/Seoul'
        code=str(row['code']).upper() if is_us else str(row['code']).zfill(6)
        bars=histories.get(code)
        if bars is None or bars.empty: continue
        bars=bars.sort_index().copy()
        try:dates=pd.to_datetime(bars.index)
        except (ValueError,TypeError,OverflowError):continue
        if dates.tz is None: dates=dates.tz_localize(zone)
        else: dates=dates.tz_convert(zone)
        clock=pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
        if clock.tzinfo is None:raise ValueError('Evaluation time requires timezone')
        # A daily bar still changing today cannot confirm a historical outcome.
        bars=bars[dates.date<clock.tz_convert(zone).date()]
        dates=dates[dates.date<clock.tz_convert(zone).date()]
        columns=['시가','고가','저가','종가']
        if bars.empty or dates.hasnans or dates.has_duplicates or any(c not in bars for c in columns):continue
        values=bars[columns].apply(pd.to_numeric,errors='coerce')
        if not np.isfinite(values.to_numpy()).all() or (values<=0).any().any():continue
        if ((values['고가']<values[['시가','종가','저가']].max(axis=1)) | (values['저가']>values[['시가','종가']].min(axis=1))).any():continue
        bars[columns]=values
        signal=pd.to_datetime(row['scan_time_utc'],errors='coerce')
        if pd.isna(signal):continue
        if signal.tzinfo is None: signal=signal.tz_localize('UTC')
        # Skip signal-day daily bar: its close may predate an intraday or after-hours signal.
        future=bars[dates.date>signal.tz_convert(zone).date()]
        for days in (1,3,5):
            if len(future)>=days:
                result.at[idx,f'd{days}_ret']=(float(future.iloc[days-1]['종가'])/entry-1)*100-cost_bps/100
        outcome='OPEN'; exit_price=None
        for _,bar in future.head(5).iterrows():
            if float(bar['시가'])<=stop: outcome='STOP_GAP'; exit_price=float(bar['시가']); break
            if float(bar['시가'])>=target: outcome='TARGET_GAP'; exit_price=float(bar['시가']); break
            if float(bar['저가'])<=stop: outcome='STOP'; exit_price=stop; break
            if float(bar['고가'])>=target: outcome='TARGET'; exit_price=target; break
        result.at[idx,'evaluation']=outcome if len(future) else 'PENDING'
        if exit_price is not None: result.at[idx,'exit_ret']=(exit_price/entry-1)*100-cost_bps/100
    return result


def walk_forward(history,code,signal_builder,min_score=60):
    """Build signals using prefixes only, simulate next open within the quoted entry zone.

    Independent overlapping scenarios; this is not a portfolio equity curve.
    """
    rows=[]
    history=history.sort_index()
    for i in range(64,len(history)-1):
        signal=signal_builder(history.iloc[:i+1].copy())
        if not signal or float(signal.get('점수',0))<min_score:continue
        entry=float(history.iloc[i+1]['시가'])
        low=float(signal.get('매수하단',0));high=float(signal.get('매수상단',0))
        stop=float(signal.get('손절가',0));target=float(signal.get('1차목표',0))
        if not 0<stop<entry<target or not low<=entry<=high:continue
        stamp=pd.Timestamp(history.index[i]).normalize()
        stamp=stamp.tz_localize('Asia/Seoul') if stamp.tzinfo is None else stamp.tz_convert('Asia/Seoul')
        stamp=stamp+pd.Timedelta(hours=15,minutes=30)
        rows.append({'code':str(code),'scan_time_utc':stamp.tz_convert('UTC').isoformat(),
                     'price':entry,'stop':stop,'tp1':target,'signal_score':signal['점수'],'entry_model':'NEXT_OPEN_WITHIN_ZONE'})
    if not rows:return pd.DataFrame()
    return evaluate_snapshots(pd.DataFrame(rows),{str(code).zfill(6):history})
