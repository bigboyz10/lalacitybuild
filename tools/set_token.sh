#!/usr/bin/env bash
# Store a GitHub token so pushes work, without ever committing it.
#
# Usage:  bash tools/set_token.sh ghp_xxxxxxxxxxxxxxxxxxxx
#    or:  bash tools/set_token.sh            (prompts, input hidden)
#
# The token is written to /home/user/.git-credentials, which sits OUTSIDE the
# workspace and is never tracked by git. The remote URL itself stays clean.
set -euo pipefail

REPO_URL="https://github.com/bigboyz10/lalacitybuild.git"
CRED="/home/user/.git-credentials"

token="${1:-}"
if [ -z "$token" ]; then
  read -r -s -p "GitHub token (input hidden): " token
  echo
fi
if [ -z "$token" ]; then
  echo "No token given." >&2
  exit 1
fi

user="$(printf '%s' "${GITHUB_USER:-bigboyz10}")"

umask 077
printf 'https://%s:%s@github.com\n' "$user" "$token" > "$CRED"
chmod 600 "$CRED"

git config --global credential.helper "store --file=$CRED"
cd "$(dirname "$0")/.."
git remote set-url origin "$REPO_URL" 2>/dev/null || git remote add origin "$REPO_URL"

echo "Token stored in $CRED (outside the workspace, not tracked)."
echo "Remote URL left clean: $(git remote get-url origin)"
echo
echo "Testing push ..."
if git push origin HEAD:refs/heads/main; then
  echo "Push succeeded - autosave will now mirror to GitHub automatically."
else
  echo "Push failed. Check the token has 'Contents: Read and write' on this repo." >&2
  exit 1
fi
