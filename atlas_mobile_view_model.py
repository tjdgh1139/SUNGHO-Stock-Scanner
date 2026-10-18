"""ATLAS compact mobile dashboard view model. Pure presentation, no invented prices.

A feed must explicitly attest verified observations before BUY-like signals
may be displayed. This module does not submit orders or touch broker secrets.
"""
from datetime import datetime, timezone

def compact_candidate(*, symbol, name, price=None, currency="KRW",
                      feed_verified=False, signal="WAIT", score=None,
                      foreign_net=None, observed_at_utc=None):
    if not isinstance(symbol,str) or not symbol.strip():
        raise ValueError("symbol required")
    if currency not in ("KRW","USD"):
        raise ValueError("unsupported currency")
    verified = feed_verified is True
    try:
        px=float(price)
        if not (0 < px < float("inf")):
            px=None
    except (ValueError,TypeError,OverflowError):
        px=None
    stamp=None
    if isinstance(observed_at_utc,str):
        try:
            stamp=datetime.fromisoformat(observed_at_utc.replace("Z","+00:00"))
            if stamp.tzinfo is None:
                stamp=None
        except (ValueError,OverflowError):
            stamp=None
    trusted = verified and px is not None and stamp is not None
    visible_signal = signal if trusted and signal in ("BUY","SELL","WAIT") else "WAIT"
    return {
        "symbol":symbol.strip(), "name":str(name).strip(),
        "price":px if trusted else None,
        "currency":currency,
        "feed_status":"VERIFIED" if trusted else "UNVERIFIED",
        "signal":visible_signal,
        "score":score if trusted and isinstance(score,(int,float)) and not isinstance(score,bool) else None,
        "foreign_net":foreign_net if trusted and isinstance(foreign_net,(int,float)) and not isinstance(foreign_net,bool) else None,
        "observed_at_utc":stamp.astimezone(timezone.utc).isoformat() if trusted else None,
        "orders_enabled":False,
    }

def compact_sections():
    return ("market_status","ranked_candidates","candidate_chart","paper_performance")
