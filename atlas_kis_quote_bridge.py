"""Read-only bridge from a verified KIS quote provider to ATLAS quote storage.

No credentials, token issuance, trade orders, or automatic scheduling here.
Use the server's existing authenticated quote function as the injected provider.
"""
from datetime import datetime, timezone
from typing import Callable, Mapping, Any
from atlas_market_quote_store import save_quote

def collect_one(db_path: str, symbol: str, provider: Callable[[str], Mapping[str, Any]],
                *, received_at_utc: str | None = None) -> bool:
    """Fetch one KRX stock snapshot and append to research DB.

    Provider contract: {'price': positive number, 'volume': optional number,
    'turnover': optional number, 'change_pct': optional number}.
    All values must come from an actual verified provider response.
    """
    if not (symbol.isdigit() and len(symbol) == 6):
        raise ValueError("KRX stock symbol must be six digits")
    quote = provider(symbol)
    if not isinstance(quote, Mapping):
        raise ValueError("provider must return a mapping")
    if "price" not in quote:
        raise ValueError("provider response has no price")
    stamp = received_at_utc or datetime.now(timezone.utc).isoformat()
    return save_quote(db_path, market="KRX", symbol=symbol, source="KIS_REST",
                      received_at_utc=stamp, price=quote["price"],
                      volume=quote.get("volume"), turnover=quote.get("turnover"),
                      change_pct=quote.get("change_pct"))
