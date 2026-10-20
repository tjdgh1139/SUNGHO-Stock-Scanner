#!/bin/sh
# Restricted GitHub Actions code sync; no Docker, sudo, shell arguments, or secrets.
set -eu
unset BASH_ENV ENV GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM
export PATH=/usr/bin:/bin
cd /home/atlasdeploy/staging/atlas
test "$(id -un)" = atlasdeploy
test "$(git branch --show-current)" = feature/atlas-paper-autosave-recovery
test -z "$(git status --porcelain)"
git fetch --no-tags origin refs/heads/feature/atlas-paper-autosave-recovery
git merge --ff-only FETCH_HEAD
git log -1 --format='%h %s'
