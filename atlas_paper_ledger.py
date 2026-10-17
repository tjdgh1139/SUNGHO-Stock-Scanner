"""ATLAS paper-trade audit ledger: reproducible, never actual orders.

Append-only JSONL event storage is handled by the caller. All trade events are
pure deterministic calculations from independently observed source timestamps.
Missing observations are UNKNOWN, not a zero return or an invented fill.
"""
from datetime import datetime, timezone
import math
from uuid import uuid4

MAX_FILL_DELAY_SECONDS=120
DEFAULT_FEE_BPS=5
DEFAULT_SLIPPAGE_BPS=10


def _utc(value):
    try:
        d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (TypeError,ValueError,OverflowError):
        return None


def _positive(x):
    try:
        v=float(x)
        return v if math.isfinite(v) and v>0 else None
    except (TypeError,ValueError,OverflowError):
        return None


def new_signal(*, market, symbol, direction, signal_time_utc, signal_price,
               stop=None, target=None, source=None, signal_id=None):
    stamp=_utc(signal_time_utc)
    px=_positive(signal_price)
    if (market not in ("KR","US") or direction!="LONG" or stamp is None
        or px is None or not isinstance(source,str) or not source.strip()):
        raise ValueError("invalid signal evidence")
    s=_positive(stop) if stop is not None else None
    t=_positive(target) if target is not None else None
    if s is not None and s>=px:
        raise ValueError("stop must be below signal")
    if t is not None and t<=px:
        raise ValueError("target must be above signal")
    if not isinstance(symbol,str) or not symbol.strip():
        raise ValueError("missing symbol")
    return {"event":"SIGNAL","id":signal_id or str(uuid4()),
            "market":market,"symbol":symbol,"direction":"LONG",
            "signal_time_utc":stamp.isoformat(),"signal_price":px,
            "stop":s,"target":t,"source":source,
            "mode":"PAPER_ONLY","status":"AWAITING_VERIFIED_FILL"}


def paper_fill(signal, quote, *, fee_bps=DEFAULT_FEE_BPS,
               slippage_bps=DEFAULT_SLIPPAGE_BPS):
    """Buy only at a later independently observed price, not signal price."""
    if signal.get("event")!="SIGNAL" or signal.get("mode")!="PAPER_ONLY":
        return None
    t0=_utc(signal.get("signal_time_utc"))
    t1=_utc(quote.get("observed_at_utc"))
    px=_positive(quote.get("price"))
    if not t0 or not t1 or px is None or not quote.get("source"):
        return None
    seconds=(t1-t0).total_seconds()
    if not 0<seconds<=MAX_FILL_DELAY_SECONDS:
        return None
    if quote.get("market")!=signal["market"] or quote.get("symbol")!=signal["symbol"]:
        return None
    if quote.get("session_date")!=t1.astimezone(
        __import__("zoneinfo").ZoneInfo("Asia/Seoul" if signal["market"]=="KR" else "America/New_York")
    ).strftime("%Y%m%d"):
        return None
    try:
        fees=float(fee_bps)
        slip=float(slippage_bps)
        if not all(math.isfinite(x) and 0<=x<=200 for x in (fees,slip)):
            return None
    except (ValueError,TypeError):
        return None
    entry=px*(1+slip/10000)
    return {"event":"PAPER_FILL","id":signal["id"],"symbol":signal["symbol"],
            "market":signal["market"],"observed_at_utc":t1.isoformat(),
            "observed_price":px,"paper_entry":entry,
            "fee_bps_per_side":fees,"slippage_bps_per_side":slip,
            "source":quote["source"],"mode":"PAPER_ONLY"}


def evaluate_paper(signal,fill,bar,*,horizon):
    """Mark paper return at 1/3/5/30min or EOD.

    High/low are only used when an actual observed bar interval is supplied.
    If stop and target both touched in the same bar, choose stop (conservative).
    This is not evidence of an executable real fill at the stop price.
    """
    if horizon not in ("1m","3m","5m","30m","EOD"):
        raise ValueError("invalid horizon")
    if not fill or fill.get("id")!=signal.get("id"):
        return None
    t0=_utc(fill.get("observed_at_utc"))
    t1=_utc(bar.get("observed_at_utc"))
    close=_positive(bar.get("close"))
    if not t0 or not t1 or t1<=t0 or close is None or not bar.get("source"):
        return None
    if bar.get("market")!=signal.get("market") or bar.get("symbol")!=signal.get("symbol"):
        return None
    # Prevent future data being evaluated as a historical horizon.
    age=(t1-t0).total_seconds()
    limits={"1m":(45,150),"3m":(150,300),"5m":(240,420),
            "30m":(1500,2100),"EOD":(1,86400)}
    lo,hi=limits[horizon]
    if not lo<=age<=hi:
        return None
    stop=signal.get("stop")
    target=signal.get("target")
    reason="MARK_TO_MARKET"
    exit_price=close
    high=_positive(bar.get("high"))
    low=_positive(bar.get("low"))
    if high is not None and low is not None and low<=close<=high:
        if stop is not None and low<=stop:
            exit_price=float(stop)
            reason="STOP_TOUCHED_CONSERVATIVE"
        elif target is not None and high>=target:
            exit_price=float(target)
            reason="TARGET_TOUCHED"
    fees=float(fill["fee_bps_per_side"])
    slip=float(fill["slippage_bps_per_side"])
    paper_exit=exit_price*(1-slip/10000)
    net_pct=((paper_exit*(1-fees/10000))/
             (float(fill["paper_entry"])*(1+fees/10000))-1)*100
    return {"event":"PAPER_OUTCOME","id":signal["id"],"horizon":horizon,
            "observed_at_utc":t1.isoformat(),"observed_close":close,
            "paper_exit":paper_exit,"net_return_pct":round(net_pct,4),
            "exit_reason":reason,"source":bar["source"],
            "mode":"PAPER_ONLY"}


def performance_summary(outcomes, *, horizon="5m"):
    selected=[r for r in outcomes if r.get("event")=="PAPER_OUTCOME"
              and r.get("horizon")==horizon and r.get("mode")=="PAPER_ONLY"
              and isinstance(r.get("net_return_pct"),(int,float))
              and math.isfinite(r["net_return_pct"])]
    if not selected:
        return {"count":0,"status":"INSUFFICIENT_DATA"}
    # Deduplicate by ID, last snapshot wins only when user supplies ordered events.
    unique={r["id"]:r for r in selected}
    vals=[r["net_return_pct"] for r in unique.values()]
    wins=[x for x in vals if x>0]
    losses=[x for x in vals if x<=0]
    return {"count":len(vals),
            "win_rate_pct":round(100*len(wins)/len(vals),2),
            "false_positive_pct":round(100*len(losses)/len(vals),2),
            "avg_net_return_pct":round(sum(vals)/len(vals),4),
            "avg_win_pct":round(sum(wins)/len(wins),4) if wins else None,
            "avg_loss_pct":round(sum(losses)/len(losses),4) if losses else None,
            "worst_trade_pct":round(min(vals),4),
            "status":"PAPER_BACKTEST_NOT_REALIZED",
            "limitations":"Selected signals only; false_positive_pct is non-profitable paper signals, not whole-market false positive rate"}
