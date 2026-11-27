#!/usr/bin/env bash
# Safe shared-main sync: commit, rebase onto origin/main, push, retry on race.
#
#   bash tools/sync.sh "what changed"
#
# Everyone commits to main, so two agents pushing at the same instant is normal
# rather than exceptional. Git ref updates are atomic: the loser of a race gets
# a non-fast-forward rejection, never a silent overwrite. This script turns that
# rejection into a rebase-and-retry, so no agent's work is ever discarded.
#
# Guarantees:
#   - never force-pushes to origin (a force push is how shared history is lost)
#   - rebases local work on top of whatever arrived first
#   - on a real conflict, aborts cleanly and names the files, leaving the tree
#     exactly as it was so a human or the agent can resolve it deliberately
set -uo pipefail

cd "$(dirname "$0")/.."

AGENT="${AGENT_ID:-$(cat /home/user/.agent-id 2>/dev/null || echo agent-unknown)}"
BRANCH="main"
TRIES="${SYNC_TRIES:-8}"
MSG="${1:-checkpoint}"

note() { printf '[sync %s] %s\n' "$AGENT" "$1"; }

# --- repair whatever the last sandbox hydration removed ---------------------
git config user.name  >/dev/null 2>&1 || git config user.name "$AGENT"
git config user.email >/dev/null 2>&1 || git config user.email "$AGENT@agents.local"
git config core.fileMode false
if ! git remote get-url origin >/dev/null 2>&1; then
  if [ -f .snapshot-remote ]; then
    git remote add origin "$(tr -d '[:space:]' < .snapshot-remote)"
  else
    note "no origin configured"; exit 1
  fi
fi

# --- commit local work ------------------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "${MSG}" -m "agent: ${AGENT}" || true
  note "committed $(git rev-parse --short HEAD)"
fi

# --- rebase onto whatever is on the remote, then push -----------------------
attempt=1
while [ "$attempt" -le "$TRIES" ]; do
  if ! git fetch -q origin "$BRANCH" 2>/dev/null; then
    note "fetch failed (offline?) - local commits are safe, will sync later"
    exit 3
  fi

  if ! git rebase -q --autostash "origin/${BRANCH}" 2>/dev/null; then
    conflicts="$(git diff --name-only --diff-filter=U | tr '\n' ' ')"
    git rebase --abort 2>/dev/null
    note "CONFLICT with another agent in: ${conflicts:-unknown}"
    note "nothing was pushed and your tree is untouched."
    note "resolve with:  git fetch origin && git rebase origin/${BRANCH}"
    exit 2
  fi

  if git push -q origin "HEAD:refs/heads/${BRANCH}" 2>/dev/null; then
    note "pushed $(git rev-parse --short HEAD) to ${BRANCH} (attempt ${attempt})"
    exit 0
  fi

  # lost the race: someone pushed between our fetch and our push
  back="0.$(( (RANDOM % 9) + 2 ))"
  note "race on ${BRANCH}, retrying in ${back}s (attempt ${attempt}/${TRIES})"
  sleep "$back"
  attempt=$((attempt + 1))
done

note "could not push after ${TRIES} attempts; local commits are safe"
exit 1
