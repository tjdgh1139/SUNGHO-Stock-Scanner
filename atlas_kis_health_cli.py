"""One-shot KIS collector with durable health record. No scheduler or orders.

Existing KIS adapter/token cache are injected via PYTHONPATH on staging server.
This script does not alter the existing production application.
"""
import argparse
import json
import os
from atlas_cycle_coordinator import run_cycle
from atlas_kis_quote_normalizer import normalize_kis_quote
from atlas_request_pacer import RequestPacer

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",required=True)
    parser.add_argument("--health-db",required=True)
    parser.add_argument("--symbols",nargs="+",required=True)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args(argv)
    symbols=list(dict.fromkeys(args.symbols))
    if not symbols or any(not (s.isascii() and s.isdigit() and len(s)==6) for s in symbols):
        parser.error("symbols must be six-digit ASCII KRX codes")
    if args.dry_run:
        print(json.dumps({"status":"DRY_RUN","symbols":symbols}))
        return 0
    key=os.environ.get("KIS_APP_KEY")
    secret=os.environ.get("KIS_APP_SECRET")
    if not key or not secret:
        print(json.dumps({"status":"CONFIGURATION_MISSING"}))
        return 3
    try:
        from atlas_kis_token_cache import get_token
        from atlas_kis_readonly import quote_request
        token=get_token(key,secret)
    except Exception as exc:
        print(json.dumps({"status":"AUTH_OR_IMPORT_FAILED","error_type":type(exc).__name__}))
        return 3
    pacer=RequestPacer(min_interval_seconds=0.5)
    def provider(symbol):
        pacer.before_request()
        return normalize_kis_quote(quote_request(symbol,key,secret,token))
    outcome=run_cycle(args.db,symbols,provider,heartbeat_db_path=args.health_db,market="KRX")
    print(json.dumps({"status":outcome.health.state,"reason":outcome.health.reason,
                      "attempted":outcome.result.attempted,"stored":outcome.result.stored,
                      "duplicates":outcome.result.duplicates,"failed":outcome.result.failed},
                     ensure_ascii=False))
    return 0 if outcome.health.state=="HEALTHY" else 2

if __name__=="__main__":
    raise SystemExit(main())
