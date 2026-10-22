"""ATLAS read-only market collection cycle.

Caller provides a list of KRX symbols and a verified KIS quote provider.
Failures are recorded per symbol and never fabricated as zero-price quotes.
No orders, no token issuance, no background daemon in this module.
"""
from dataclasses import dataclass, field
from typing import Callable, Mapping, Any, Iterable
from atlas_kis_quote_bridge import collect_one

@dataclass
class CycleResult:
    attempted: int = 0
    stored: int = 0
    duplicates: int = 0
    failed: dict[str, str] = field(default_factory=dict)

def collect_cycle(db_path: str, symbols: Iterable[str],
                  provider: Callable[[str], Mapping[str, Any]],
                  *, received_at_utc: str | None = None,
                  stop_on: tuple[type[Exception], ...] = ()) -> CycleResult:
    result = CycleResult()
    for symbol in dict.fromkeys(symbols):
        result.attempted += 1
        try:
            inserted = collect_one(db_path, symbol, provider,
                                   received_at_utc=received_at_utc)
            if inserted:
                result.stored += 1
            else:
                result.duplicates += 1
        except Exception as exc:
            # Avoid logging provider exception details: some SDKs include secrets.
            result.failed[str(symbol)] = type(exc).__name__
            if isinstance(exc, stop_on):
                break
    return result
