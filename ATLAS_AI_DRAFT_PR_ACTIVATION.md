# ATLAS AI Draft-PR Agent — activation checklist

Status: NOT ENABLED. The existing nightly GitHub Action runs read-only tests only.

## Required before enabling autonomous code writing
- Select and authorize an AI coding runtime (e.g. Codex) and its billing / usage ceiling.
- Store credentials only in GitHub Actions secrets or a scoped GitHub App, never in code or artifacts.
- Grant the coding runner access only to an isolated development branch and draft pull requests.
- Keep production and staging server SSH keys, KIS credentials, and brokerage order permissions inaccessible to the runner.
- Limit to one task per run, bounded runtime and changes, no recursive agent spawning.
- Require passing CI and human review before merging, deploying, or changing trading logic.
- Emit a run report with issue/task, diff summary, tests, costs where available, and failure reason.
- Fail closed if credentials, quota, approvals, or test results are unavailable.

## First safe pilot
A manually triggered coding job may improve unit tests or documentation only and open a draft PR.
It must never auto-merge. Daily autonomous writing should be enabled only after a successful pilot.
