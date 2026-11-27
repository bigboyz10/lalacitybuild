#!/usr/bin/env bash
# Rebuild the workspace after a wipe.
# Usage: bash restore.sh [target-dir]      (default: /home/user/workspace)
#
# GitHub is the only copy that survives a full sandbox reset, so it is tried
# first; the in-sandbox mirror is the fallback when the network or the token
# is unavailable.
set -euo pipefail

MIRROR="/home/user/.workspace-backup/repo.git"
ORIGIN="https://github.com/bigboyz10/lalacitybuild.git"
TARGET="${1:-/home/user/workspace}"

SOURCE=""
if git ls-remote "$ORIGIN" >/dev/null 2>&1; then
  SOURCE="$ORIGIN"
  echo "Restoring from GitHub (survives a sandbox reset)."
elif [ -d "$MIRROR" ]; then
  SOURCE="$MIRROR"
  echo "GitHub unreachable - restoring from the local mirror."
else
  echo "No source available: GitHub unreachable and no mirror at ${MIRROR}." >&2
  exit 1
fi

mkdir -p "$TARGET"
if [ -d "$TARGET/.git" ]; then
  echo "Repo already present in ${TARGET}; fetching any missing history."
  git -C "$TARGET" fetch -q "$SOURCE" 'refs/heads/*:refs/remotes/recovered/*'
  echo "Recovered history is under refs/remotes/recovered/*."
else
  git clone -q "$SOURCE" "$TARGET"
  echo "Restored ${TARGET} from ${SOURCE}."
fi

git -C "$TARGET" config user.name "Workspace"
git -C "$TARGET" config user.email "workspace@localhost"
git -C "$TARGET" config core.fileMode false
git -C "$TARGET" log --oneline | head -5
