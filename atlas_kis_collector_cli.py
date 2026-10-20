"""Read-only, one-shot ATLAS KIS market collector CLI.

Run only on a server with atlas_kis_readonly and atlas_kis_token_cache
already installed and KIS credentials provided securely as environment vars.
Never imports trading/order functions. No daemon and no implicit execution.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from atlas_market_collection import collect_cycle


def main(argv=None):
    parser=argparse.ArgumentParser(description="One-shot read-only KIS quote collection")
    parser.add_argument("--db", required=True)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args=parser.parse_args(argv)
    symbols=list(dict.fromkeys(args.symbols))
    if any(not (s.isdigit() and len(s)==6) for s in symbols):
        parser.error("all symbols must be six-digit KRX codes")
    if args.dry_run:
        print(json.dumps({"mode":"DRY_RUN","symbols":symbols,"db":args.db}))
        return 0
    # Import live broker integrations only for explicitly requested execution.
    from atlas_kis_token_cache import get_token
    from atlas_kis_readonly import quote_request
    from atlas_kis_quote_normalizer import normalize_kis_quote
    key=os.environ.get("KIS_APP_KEY")
    secret=os.environ.get("KIS_APP_SECRET")
    if not key or not secret:
        raise RuntimeError("KIS credentials are not configured")
    token=get_token(key,secret)
    def provider(symbol):
        quote=quote_request(symbol,key,secret,token)
        return normalize_kis_quote(quote)
    report=collect_cycle(args.db,symbols,provider)
    print(json.dumps({"attempted":report.attempted,"stored":report.stored,
                      "duplicates":report.duplicates,"failed":report.failed}))
    return 0 if not report.failed else 2


if __name__=="__main__":
    raise SystemExit(main())
