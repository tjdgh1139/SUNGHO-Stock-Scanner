# ATLAS unattended development — safety contract

Current phase: read-only scheduled CI audit. This is NOT an autonomous code-writing agent.

## Planned phases
1. Scheduled offline regression tests and artifact retention (implemented in staging workflow).
2. Add an explicitly authorized AI coding runner in an isolated branch, with a narrowly scoped credential, spending limits, bounded execution time, and no access to KIS secrets or production server.
3. AI may open draft pull requests only; branch protection, human review, and passing CI required.
4. No automatic production deployment, order placement, secret changes, or strategy promotion.
5. Log task intent, diff, tests, model costs, and rollback plan for every proposed change.

## Activation notes
GitHub Actions scheduled workflows execute from the repository default branch.
This workflow is currently in atlas/market-data-storage-staging; scheduling is not live until reviewed and merged into the default branch.
No Codex/API key or autonomous write permission is configured by this change.
