# ATLAS stability-first staging

**NOT DEPLOYED.** This Compose stack runs a durable local health heartbeat only.
It does not connect to KIS, subscribe to ticks, place trades, or claim live
market coverage. Production Streamlit remains unchanged.

Suggested first host: DigitalOcean Basic 2vCPU/4GiB/80GiB ($24/mo listed).
Before provisioning: obtain owner billing approval, SSH access, and KIS
credentials via a secret manager; never commit keys.

On an authorized Linux host with Docker Compose:
```sh
docker compose -f deploy/atlas-paper/compose.yaml up -d --build
docker compose -f deploy/atlas-paper/compose.yaml ps
```

A named Docker volume preserves SQLite records across container restarts, but
**not** across loss of the host disk. Configure encrypted off-host backups,
restore drills, resource monitoring, firewall rules, and alerts separately.
No ports are exposed. Production feed adapter must be separately implemented,
verified and authorized before any live observations are enabled.

Next gates: offline CI green; verified KR/US exchange calendars; KIS feed
entitlements; durable paper-event sink; supervised reconnect; staging across
full market sessions. No real trading without separate explicit approval.
