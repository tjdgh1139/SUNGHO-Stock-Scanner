"""Strict KIS quote response normalization (read-only).

Accepts known KIS domestic stock current-price output keys only.
Never substitutes missing fields with zero or claims an exchange timestamp.
"""
from decimal import Decimal, InvalidOperation

def _number(raw, *, required=False):
    if raw is None or str(raw).strip()=="":
        if required:
            raise ValueError("missing required numeric field")
        return None
    try:
        value=Decimal(str(raw).replace(",",""))
    except (InvalidOperation,ValueError):
        raise ValueError("invalid numeric field") from None
    if not value.is_finite():
        raise ValueError("nonfinite numeric field")
    return float(value)

def normalize_kis_quote(response: dict) -> dict:
    if not isinstance(response,dict):
        raise ValueError("KIS response must be a mapping")
    # Some KIS adapters return the full REST response, others only output.
    if "rt_cd" in response and str(response["rt_cd"])!="0":
        raise ValueError("KIS returned an unsuccessful result")
    data=response.get("output",response)
    if not isinstance(data,dict):
        raise ValueError("KIS output must be an object")
    price=_number(data.get("stck_prpr",data.get("price",data.get("현재가"))),required=True)
    if price<=0:
        raise ValueError("nonpositive price")
    volume=_number(data.get("acml_vol",data.get("volume",data.get("누적거래량"))))
    turnover=_number(data.get("acml_tr_pbmn",data.get("turnover",data.get("누적거래대금"))))
    change_pct=_number(data.get("prdy_ctrt",data.get("change_pct",data.get("등락%",data.get("등락률")))))
    if volume is not None and volume<0:
        raise ValueError("negative volume")
    if turnover is not None and turnover<0:
        raise ValueError("negative turnover")
    return {"price":price,"volume":volume,"turnover":turnover,"change_pct":change_pct}
