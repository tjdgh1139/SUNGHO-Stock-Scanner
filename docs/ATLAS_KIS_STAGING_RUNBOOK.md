# ATLAS KIS collector staging runbook

**Scope:** research/paper only. No broker orders, no production deployment.
Do not commit secrets, tokens, or the SQLite database to Git.

## Preconditions

- The operator verifies that the checkout is on `atlas/market-data-storage-staging`, not `main`.
- The server already has the read-only KIS integration and token cache module.
- KIS credentials are loaded into the shell securely without printing them.
- The server clock is synchronized, and the KIS market-data permissions are valid.
- The actual signature and response format of `atlas_kis_readonly.quote_request` must be checked against the deployed version before running a live request.

## Dry run (no API requests, no orders)

```bash
python atlas_kis_collector_cli.py --db /opt/atlas/data/market_quotes.sqlite --symbols 000660 005930 --dry-run
```

## Live read-only verification (operator-triggered only)

Only after checking the adapter signature and credentials:

```bash
python atlas_kis_collector_cli.py --db /opt/atlas/data/market_quotes.sqlite --symbols 000660 005930
```

The command requests market data, not orders. Verify the exit code, stored row count, data-source fields, UTC receipt timestamps, quote age, and DB permissions. Do not infer real-time coverage from a single successful response. Start with two symbols, then increase within broker API rate limits.

## Go/no-go

Do not schedule continuous collection until the following are confirmed: correct KIS response normalization, successful authenticated read-only quote retrieval, repeat-run token reuse, database persistence across restarts, safe handling of missing/stale quotes, session awareness and API rate limits, and monitored failure recovery.

**Do not merge the PR into main or deploy to Streamlit without review.**
