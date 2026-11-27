#!/usr/bin/env bash
# Continuous autosave for a SHARED main branch.
#
#   bash autosave.sh
#
# Checks the workspace every second. When something changes it commits, mirrors
# outside the workspace, and syncs to origin/main through tools/sync.sh, which
# rebases rather than forcing so a concurrent agent's work is never discarded.
#
# Two behaviours matter when several agents share main:
#
#   * Coalescing. Consecutive autosave commits that have not yet reached the
#     remote are amended into one instead of piling up a commit per second.
#     Shared history stays readable.
#   * Backing off on conflict. If a rebase hits a real conflict the loop stops
#     pushing and says so, rather than retrying every second and burying the
#     message. Local commits keep accumulating safely in the meantime.
set -uo pipefail

cd "$(dirname "$0")"
AGENT="${AGENT_ID:-$(cat /home/user/.agent-id 2>/dev/null || echo agent-unknown)}"
MIRROR="/home/user/.workspace-backup/repo.git"
INTERVAL="${AUTOSAVE_INTERVAL:-1}"
PUSH_EVERY="${AUTOSAVE_PUSH_EVERY:-10}"     # seconds between remote syncs
LOG="/home/user/.workspace-backup/autosave.log"

mkdir -p "$(dirname "$MIRROR")"
[ -d "$MIRROR" ] || git init -q --bare "$MIRROR"

log() { printf '%s %s\n' "$(date -u '+%H:%M:%S')" "$1" | tee -a "$LOG"; }

repair() {
  if ! git config user.email >/dev/null 2>&1; then
    git config user.name "$AGENT"
    git config user.email "$AGENT@agents.local"
    git config core.fileMode false
    log "repaired identity (hydration wiped .git/config)"
  fi
  if [ -f .snapshot-remote ] && ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$(tr -d '[:space:]' < .snapshot-remote)"
    log "repaired origin"
  fi
}

# True when HEAD is one of our own autosave commits that we have not synced
# yet. Deliberately answered from local state: the earlier version fetched from
# origin on every tick, which is a network round-trip per second per agent.
can_amend() {
  [ "$(git rev-parse HEAD 2>/dev/null)" != "$last_synced" ] || return 1
  git log -1 --format='%s' 2>/dev/null | grep -q "^autosave(${AGENT})"
}

log "autosave started (every ${INTERVAL}s, sync every ${PUSH_EVERY}s) agent=${AGENT} pid=$$"
last_push=0
conflict_state=0
last_synced="$(git rev-parse HEAD 2>/dev/null || echo none)"

while true; do
  repair
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    git add -A 2>/dev/null
    msg="autosave(${AGENT}) $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    if can_amend; then
      git commit -q --amend -m "$msg" 2>/dev/null && log "coalesced into $(git rev-parse --short HEAD)"
    else
      git commit -q -m "$msg" 2>/dev/null && log "saved $(git rev-parse --short HEAD)"
    fi
    git push -q --force "$MIRROR" HEAD:refs/heads/main 2>/dev/null || true
  fi

  now=$(date +%s)
  if [ -n "$(git log origin/main..HEAD --oneline 2>/dev/null)" ] \
     && [ $((now - last_push)) -ge "$PUSH_EVERY" ]; then
    out="$(bash tools/sync.sh "autosave(${AGENT})" 2>&1)"
    rc=$?
    last_push=$now
    case "$rc" in
      0) log "synced to origin/main"; conflict_state=0
         last_synced="$(git rev-parse HEAD)" ;;
      2) if [ "$conflict_state" -eq 0 ]; then
           log "PAUSED: $(printf '%s' "$out" | grep CONFLICT | head -1)"
           log "  commits are safe locally; resolve, then autosave resumes"
           conflict_state=1
         fi
         last_push=$((now + 50)) ;;
      *) log "sync deferred (rc=$rc)" ;;
    esac
  fi
  sleep "$INTERVAL"
done
