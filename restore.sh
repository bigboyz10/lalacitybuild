#!/usr/bin/env bash
# Rebuild the workspace from the mirror after a wipe.
# Usage: bash restore.sh [target-dir]      (default: /home/user/workspace)
set -euo pipefail

MIRROR="/home/user/.workspace-backup/repo.git"
TARGET="${1:-/home/user/workspace}"

if [ ! -d "$MIRROR" ]; then
  echo "No mirror at ${MIRROR} — nothing to restore from." >&2
  exit 1
fi

mkdir -p "$TARGET"
if [ -d "$TARGET/.git" ]; then
  echo "Repo already present in ${TARGET}; fetching any missing history."
  git -C "$TARGET" fetch -q "$SOURCE" 'refs/heads/*:refs/remotes/recovered/*'
  echo "Recovered history available under refs/remotes/recovered/*."
else
  git clone -q "$SOURCE" "$TARGET"
  echo "Restored ${TARGET} from ${SOURCE}."
fi

git -C "$TARGET" config user.name "Workspace"
git -C "$TARGET" config user.email "workspace@localhost"
git -C "$TARGET" config core.fileMode false
git -C "$TARGET" log --oneline | head -5
