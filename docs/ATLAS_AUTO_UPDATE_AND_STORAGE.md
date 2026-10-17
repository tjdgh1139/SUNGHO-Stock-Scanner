# ATLAS automatic updates and paper journal

## What works automatically when the Streamlit page is open
- Preopen published KR TOP5 is loaded without pressing Scan, with 45-second cache refresh.
- A frozen preopen candidates and B dynamic early-momentum candidates are displayed separately.
- B re-evaluates every 2 seconds using the last received data. A KIS WebSocket trade is **not** assumed to occur every 2 seconds.
- Paper-only signals require verified fresh KIS trade/book/program source data. Fills require a **later, distinct** trade. 1/3/5/30-minute paper returns include assumed fees and slippage. These are hypothetical, not realized.
- New-day automatic preopen candidates replace yesterday's manual picks; same-day manual picks remain preserved.

## Optional SQLite auto-save
Configure BOTH environment variables on the server:

- `ATLAS_PAPER_DB_PATH` — absolute path on a **persistent mounted disk** (for example `/var/lib/atlas/paper.sqlite3`)
- `ATLAS_PAPER_NAMESPACE` — stable private namespace for this one account/session owner

When configured, each emitted paper event is saved atomically using SQLite WAL and deduplicated by signal/fill/horizon. The journal is loaded automatically at session initialization. Failures are shown and pending events are retried while the page remains open.

**Streamlit Community Cloud local filesystem is not guaranteed durable.** Do not claim permanent storage unless a persistent volume or managed database has been configured and tested. Do not put API keys, passwords or personal identifiers in the namespace. Do not share a namespace across unrelated users.

## Still required for unattended 24/7 operation
- A persistent market-hours collector service independent of browser sessions, with official authorized real-time market feeds.
- Confirm actual KIS subscription acknowledgments and fresh trade/book/program receipts in NXT and KRX sessions.
- Add verified US trade feed before US paper fills.
- Add EOD bar collection, true stop/target path evaluation, data completeness reports, and independent out-of-sample strategy comparisons.
- Observe broker data-license limits and API rate limits. No real orders are issued.

GitHub Actions scheduled preopen EOD snapshots are a separate automation and **do not** constitute a continuous live market-data service.
