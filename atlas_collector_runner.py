"""ATLAS standalone paper collector runner (offline-safe orchestration).

The runner is deliberately broker-neutral. Inject a real authenticated source
and a durable event sink in deployment; never synthesize trades or place orders.
"""
from datetime import datetime, timezone
import time
from atlas_collector_watchdog import collector_health

def poll_once(source, sink, *, now=None):
    """One bounded polling cycle; no trading and no fake success on errors.

    source() must return a mapping containing authenticated heartbeat/trade
    timestamps and a nonnegative verified symbol count.
    sink(record) must persist the diagnostic event, or raise.
    """
    now = now or datetime.now(timezone.utc)
    snapshot = source()
    if not isinstance(snapshot, dict):
        raise ValueError("source must return a mapping")
    health = collector_health(
        connected=snapshot.get("connected") is True,
        heartbeat_utc=snapshot.get("heartbeat_utc"),
        latest_trade_utc=snapshot.get("latest_trade_utc"),
        verified_symbols=snapshot.get("verified_symbols"),
        now=now,
    )
    record = {"event":"COLLECTOR_HEALTH","observed_at_utc":now.isoformat(),
              **health}
    sink(record)
    return record

def run_forever(source, sink, *, interval_seconds=2, stop=None,
                on_error=None):
    """Sequential collector loop with bounded backoff; host owns scheduling.

    Errors are reported and never interpreted as verified market data.
    """
    if not 1 <= interval_seconds <= 60:
        raise ValueError("interval_seconds must be between 1 and 60")
    failures = 0
    while stop is None or not stop():
        try:
            poll_once(source, sink)
            failures = 0
        except Exception as exc:
            failures += 1
            if on_error is not None:
                on_error(type(exc).__name__)
        delay = min(60, interval_seconds * (2 ** min(failures, 5)))
        time.sleep(delay)
