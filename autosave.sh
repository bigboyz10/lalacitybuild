#!/usr/bin/env bash
# Continuous autosave. Checks the workspace every second; the moment anything
# changes it commits and mirrors outside the workspace (and pushes if origin
# accepts credentials). Start:  bash autosave.sh
set -uo pipefail

cd "$(dirname "$0")"
MIRROR="/home/user/.workspace-backup/repo.git"
INTERVAL="${AUTOSAVE_INTERVAL:-1}"

# With several agents sharing the repo, pushing every commit to main would make
# everyone else's push non-fast-forward and silently stall their autosave.
# When AGENT_ID is set we push to a per-agent branch instead; main is then only
# ever written through agents/agentctl.py.
AGENT_ID="${AGENT_ID:-}"
if [ -n "$AGENT_ID" ]; then
  PUSH_REF="refs/heads/agent/${AGENT_ID}/autosave"
else
  PUSH_REF="refs/heads/main"
fi
LOG="/home/user/.workspace-backup/autosave.log"

mkdir -p "$(dirname "$MIRROR")"
[ -d "$MIRROR" ] || git init -q --bare "$MIRROR"

log() { printf '%s %s\n' "$(date -u '+%H:%M:%S')" "$1" | tee -a "$LOG"; }

repair() {
  if ! git config user.email >/dev/null 2>&1; then
    git config user.name "Workspace"
    git config user.email "workspace@localhost"
    git config core.fileMode false
    log "repaired identity (hydration wiped .git/config)"
  fi
  if [ -f .snapshot-remote ] && ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$(tr -d '[:space:]' < .snapshot-remote)"
    log "repaired origin"
  fi
}

log "autosave started (every ${INTERVAL}s) pid=$$ -> ${PUSH_REF##refs/heads/}"
push_fail_logged=0

while true; do
  repair
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    git add -A 2>/dev/null
    if git commit -q -m "autosave $(date -u '+%Y-%m-%d %H:%M:%S UTC')" 2>/dev/null; then
      sha="$(git rev-parse --short HEAD)"
      git push -q --force "$MIRROR" HEAD:refs/heads/main 2>/dev/null \
        && log "saved $sha -> workspace + repo + mirror" \
        || log "saved $sha -> workspace + repo (mirror push failed)"
      if git remote get-url origin >/dev/null 2>&1; then
        if git push -q origin "HEAD:${PUSH_REF}" 2>/dev/null; then
          log "  pushed $sha to origin ${PUSH_REF##refs/heads/}"
          push_fail_logged=0
        elif [ "$push_fail_logged" -eq 0 ]; then
          log "  origin push needs credentials - local copies still safe"
          push_fail_logged=1
        fi
      fi
    fi
  fi
  sleep "$INTERVAL"
done
