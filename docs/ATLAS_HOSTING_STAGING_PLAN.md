# ATLAS unattended collector deployment — staging checklist

Status: **NOT DEPLOYED**. This is an infrastructure plan, not a live service.

## Recommended architecture
- Dedicated small always-on Linux host running a supervised Python worker
- Persistent managed PostgreSQL or attached durable volume for paper events
- Streamlit Cloud remains read-only presentation
- Secrets stored only in host secret manager (never GitHub or logs)
- Collector account has no trade permissions; PAPER_ONLY enforced
- Separate KRX/NXT/US authenticated feed adapters; never use REST receipt time as exchange trade time
- Exchange calendar, early closes, holidays and KIS rate limits must be verified before enabling a venue

## Deployment gates
1. Run all offline unit/integration tests and inspect CI results.
2. Verify broker KIS API entitlement, websocket subscription limits, timestamps and reconnect behavior.
3. Select host/provider and provision persistent storage; configure backup/restore.
4. Configure service supervisor with restart policy, exponential backoff and alerting.
5. Run staging for one full KR and US session with verified event logs; no real orders.
6. Compare observed paper fills and P&L to source ticks; missing feed => UNKNOWN, not zero.
7. Obtain explicit approval before changing production Streamlit deployment.

## Operational warnings
- Streamlit session fragments are **not** an always-on backend.
- SQLite on an ephemeral cloud filesystem is **not** durable.
- No account, server, cloud billing or API key is provisioned by this document.
- A calendar time window alone is insufficient to authorize a live market signal.
