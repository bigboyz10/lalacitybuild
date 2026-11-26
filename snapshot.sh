#!/usr/bin/env bash
# Save the workspace: commit to the repository, mirror outside the workspace,
# and push to a remote when one is configured.
#
# Usage: bash snapshot.sh ["message"]
#
# Hydration between turns has been observed deleting .git/config (identity and
# remotes) and stripping executable bits. Everything below is written to survive
# that: the mirror path is hardcoded rather than read from config, and identity
# and remotes are restored automatically.
set -euo pipefail

cd "$(dirname "$0")"
MIRROR="/home/user/.workspace-backup/repo.git"   # outside the workspace: hydration cannot reach it
REMOTE_FILE=".snapshot-remote"                   # tracked, so an origin URL survives a config wipe

# --- repair anything hydration removed -------------------------------------
if ! git config user.email >/dev/null 2>&1; then
  git config user.name "Workspace"
  git config user.email "workspace@localhost"
  git config core.fileMode false
  echo "Repaired git identity (hydration had wiped .git/config)."
fi

if [ -f "$REMOTE_FILE" ] && ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$(tr -d '[:space:]' < "$REMOTE_FILE")"
  echo "Repaired origin from ${REMOTE_FILE}."
fi

if git remote get-url origin >/dev/null 2>&1; then
  url="$(git remote get-url origin)"
  if [ ! -f "$REMOTE_FILE" ] || [ "$(tr -d '[:space:]' < "$REMOTE_FILE")" != "$url" ]; then
    printf '%s\n' "$url" > "$REMOTE_FILE"
    echo "Recorded origin in ${REMOTE_FILE}."
  fi
fi

# --- commit -----------------------------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  message="${1:-checkpoint}"
  git add -A
  git commit -q -m "snapshot: ${message} ($(date -u '+%Y-%m-%d %H:%M UTC'))"
  echo "Committed $(git rev-parse --short HEAD) — ${message}"
else
  echo "Working tree clean — nothing new to commit."
fi

# --- copy 2: mirror outside the workspace -----------------------------------
mkdir -p "$(dirname "$MIRROR")"
[ -d "$MIRROR" ] || git init -q --bare "$MIRROR"
git push -q --force "$MIRROR" HEAD:refs/heads/main
echo "Mirrored to ${MIRROR} (survives a workspace wipe)."

# --- copy 3: off-sandbox remote ---------------------------------------------
if git remote get-url origin >/dev/null 2>&1; then
  if git push -q origin HEAD 2>/dev/null; then
    echo "Pushed to origin (survives a full sandbox reset)."
  else
    echo "WARNING: push to origin failed — only local copies exist."
  fi
else
  echo "No origin set — safe against workspace wipes, NOT against a sandbox reset."
  echo "  Add one with: git remote add origin <url> && bash snapshot.sh"
fi
