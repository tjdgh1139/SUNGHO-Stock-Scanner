# ATLAS isolated paper store smoke

This is a separate staging Compose project. It does not alter or restart the
existing atlas-paper-staging service. No KIS credentials, feeds or real orders.

Run from repository root:
```bash
docker compose -f deploy/atlas-paper/paper-smoke/compose.yaml config -q
docker compose -f deploy/atlas-paper/paper-smoke/compose.yaml up -d --build
docker compose -f deploy/atlas-paper/paper-smoke/compose.yaml ps
docker compose -f deploy/atlas-paper/paper-smoke/compose.yaml logs --tail=10
```
Expected: PAPER_STAGING_NO_FEED_OK. The named volume persists across
container restarts, but this only checks no-feed safety; it does not test
persisting/recovering a real paper event. No public ports are exposed.
