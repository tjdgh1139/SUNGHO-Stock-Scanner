"""ATLAS session-scoped paper-trade stream from independently received quotes.

A: frozen preopen candidates, B: dynamically ranked prebreakout candidates.
Only authenticated, fresh KIS WS KR observations are currently eligible for
simulated fills. US ranking REST receipts are NOT exchange trade timestamps,
so US candidates remain unfilled until an authenticated feed is integrated.
Never places an order; never calls a signal a realized trade.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from atlas_paper_ledger import new_signal, paper_fill, evaluate_paper, performance_summary

KST=ZoneInfo("Asia/Seoul")
HORIZONS=("1m","3m","5m","30m")
HORIZON_RANGES={"1m":(45,150),"3m":(150,300),"5m":(240,420),"30m":(1500,2100)}
MAX_QUOTE_AGE=10
MAX_SIGNAL_PER_SESSION=60


def _utc(s):
    if not isinstance(s,str):
        return None
    try:
        dt=datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError,OverflowError):
        return None


def validated_kr_trade(code, row, *, now, venue):
    """Require live trade/book/program verification and a matching market date."""
    if not isinstance(row,dict):
        return None
    stamp=_utc(row.get("trade_received_utc"))
    if stamp is None or not 0<=(now-stamp).total_seconds()<=MAX_QUOTE_AGE:
        return None
    if row.get("market_date")!=now.astimezone(KST).strftime("%Y%m%d"):
        return None
    if venue=="J":
        from atlas_ws_panel import live_state
        if live_state(row,True,now)!="실시간 수신 확인":
            return None
    elif venue=="NX":
        from atlas_nxt_revalidation import nxt_fresh_quote
        if nxt_fresh_quote(row,now=now) is None:
            return None
    else:
        return None
    try:
        price=float(row["현재가"])
        if not 0<price<1e10:
            return None
    except (ValueError,TypeError,KeyError):
        return None
    return {"market":"KR","symbol":code,"price":price,
            "observed_at_utc":stamp.isoformat(),
            "session_date":now.astimezone(KST).strftime("%Y%m%d"),
            "source":"KIS WS "+venue+" verified trade receipt"}


def empty_ledger():
    return {"signals":{},"fills":{},"outcomes":{},"events":[],
            "last_trade_stamp":{}}


def step_ledger(state, *, a_candidates=(), b_candidates=(), ws_rows=None,
                connected=False, venue=None, now=None):
    """Process one new quote tick; return (updated_state, newly emitted events).

    Mutates a caller-owned in-memory state. The caller must persist emitted
    events separately if continuity across restarts is required.
    """
    now=now or datetime.now(timezone.utc)
    ws_rows=ws_rows or {}
    emitted=[]
    if not connected or venue not in ("J","NX"):
        return state,emitted
    observed={}
    for code,row in ws_rows.items():
        quote=validated_kr_trade(str(code),row,now=now,venue=venue)
        if quote is not None:
            observed[str(code)]=quote
    day=now.astimezone(KST).strftime("%Y%m%d")
    # Do not create duplicate signals when a 2s fragment redraws the same tick.
    for origin,candidates in (("A",a_candidates),("B",b_candidates)):
        for item in candidates:
            code=str(item.get("symbol") or item.get("코드") or "")
            q=observed.get(code)
            if q is None:
                continue
            key=f"{day}:KR:{origin}:{code}"
            if key in state["signals"] or len(state["signals"])>=MAX_SIGNAL_PER_SESSION:
                continue
            # Signal requires a fresh, independently authenticated observation.
            try:
                signal=new_signal(
                    market="KR",symbol=code,direction="LONG",
                    signal_time_utc=q["observed_at_utc"],signal_price=q["price"],
                    stop=item.get("stop"),target=item.get("target"),
                    source=q["source"]+"; candidate "+origin,
                    signal_id=key)
            except (ValueError,TypeError):
                continue
            signal["origin"]=origin
            signal["candidate_score"]=item.get("예비점수",item.get("score"))
            state["signals"][key]=signal
            state["events"].append(signal)
            emitted.append(signal)
    # Every fill must use a subsequent distinct observed tick, never the
    # signal tick or the current screen's last-price re-render.
    for key,signal in list(state["signals"].items()):
        q=observed.get(signal["symbol"])
        if q is None:
            continue
        if key not in state["fills"]:
            fill=paper_fill(signal,q)
            if fill is not None:
                state["fills"][key]=fill
                state["events"].append(fill)
                emitted.append(fill)
            continue
        fill=state["fills"][key]
        for horizon in HORIZONS:
            outcome_key=(key,horizon)
            if outcome_key in state["outcomes"]:
                continue
            t0=_utc(fill["observed_at_utc"])
            t1=_utc(q["observed_at_utc"])
            if t0 is None or t1 is None:
                continue
            elapsed=(t1-t0).total_seconds()
            lo,hi=HORIZON_RANGES[horizon]
            if not lo<=elapsed<=hi:
                continue
            # Only an observed tick, not a fabricated intraminute high/low.
            bar={"market":"KR","symbol":signal["symbol"],
                 "observed_at_utc":q["observed_at_utc"],
                 "close":q["price"],"source":q["source"]}
            outcome=evaluate_paper(signal,fill,bar,horizon=horizon)
            if outcome:
                state["outcomes"][outcome_key]=outcome
                state["events"].append(outcome)
                emitted.append(outcome)
    return state,emitted


def session_report(state):
    outcomes=list(state["outcomes"].values())
    return {h:performance_summary(outcomes,horizon=h) for h in HORIZONS}
