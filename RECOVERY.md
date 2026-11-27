# Recovery Report

**Date:** 2026-11-26
**Request:** Recover work lost from a previous session.
**Outcome:** Unrecoverable in this sandbox. No deletion occurred here — the workspace was never populated.

## Evidence

| Check | Location | Result |
|---|---|---|
| Workspace contents | `/home/user/workspace` | Empty at session start (0 entries) |
| Session baseline snapshot | `/tmp/arena-workspace/baseline.json` | `{"files":{}}` |
| Session input files | `/tmp/arena-workspace/baseline-input.json` | `{"files":{}}` |
| Hydration archive | `/tmp/arena-workspace/hydrate.zip` | 22 bytes — empty zip |
| Git repositories | filesystem-wide, depth 6 | None |
| Project manifests | `package.json`, `pyproject.toml`, `Cargo.toml` | Only toolchain-internal |
| Editor swap/backup files | `*.swp`, `*~`, `.#*` | None |
| Trash directory | `~/.local/share/Trash` | Does not exist |
| Deleted-but-open file handles | `/proc/*/fd` | None |
| Recently modified user files | filesystem-wide, last 14 days | Only platform files above |
| Overlay filesystem lower layer | `/proc/mounts` | None — plain ext4 on `/dev/vda`, no layer to mine |
| Raw block undelete | root mount options | `discard` (TRIM) active — freed blocks erased |
| Forensic tooling | `extundelete`, `debugfs`, `testdisk`, `photorec` | Not installed |

## Interpretation

The baseline snapshot records workspace state at session start; it is empty, and the hydration
archive carries no payload. Two independent avenues were then ruled out: there is **no overlayfs
lower layer** (the root is a plain ext4 volume, so no prior container layer retains old data), and
the volume mounts with **`discard`**, meaning freed blocks are TRIMmed and raw undelete is not
viable even with tooling.

The prior work therefore lived in a **different sandbox that was reset**, or existed only in chat
and was never written to disk. A reset is destructive and cannot be rolled back from inside.

## Ways to restore

1. **From chat history** — paste the file contents; they get written straight back.
2. **From a Git remote** — if it was ever pushed, clone and resume from the last commit.
3. **Rebuild** — describe the stack and layout; reconstruction is usually fast.

## Preventing recurrence

Three copies now exist, each defeating a different failure mode.

| # | Copy | Location | Survives |
|---|---|---|---|
| 1 | Working tree | `/home/user/workspace` | normal turns |
| 2 | Git repository | `/home/user/workspace/.git` | file edits, deletions, bad changes |
| 3 | Mirror | `/home/user/.workspace-backup/repo.git` | a workspace wipe (sits outside the workspace) |
| 4 | Remote *(not set)* | off-sandbox | a full sandbox reset |

Save all copies at once:

```bash
bash snapshot.sh "what changed"
```

Restore after a wipe:

```bash
bash restore.sh              # rebuilds /home/user/workspace from the mirror
```

### Hydration damage, and how it is handled

Hydration between turns was observed doing two destructive things. Both are now neutralised.

- **Deleting `.git/config`** — taking the commit identity and any configured remote with it.
  Commits survived (they live in `.git/objects`), but `git commit` failed outright with
  *"Author identity unknown"*, and a hand-added `origin` vanished silently so pushes stopped
  without warning. **Fix:** identity is set in `/home/user/.gitconfig`, which lives *outside* the
  workspace and is therefore out of hydration's reach; `snapshot.sh` additionally repairs the
  local config and restores `origin` from the tracked `.snapshot-remote` file. Verified by
  deleting `.git/config` and confirming a plain `git commit` still succeeds.
- **Stripping executable bits** (`100755` -> `100644`), which broke `./snapshot.sh` and produced a
  phantom modification on every turn. **Fix:** `core.fileMode=false` globally, so the churn is
  ignored. Invoke scripts as `bash snapshot.sh` to be safe regardless of the bit.

The mirror path is hardcoded inside `snapshot.sh` rather than stored as a git remote, precisely so
a config wipe cannot sever it.

### Gap closed: off-sandbox backup is live

`origin` is `https://github.com/bigboyz10/lalacitybuild.git` and pushing works.
GitHub is the only copy that survives a full sandbox reset, and three resets
have already occurred during this project — each one destroyed the local
mirror, the global git config and the Blender install, while the workspace
itself was rehydrated from tracked files only. Anything gitignored (`build/`,
renders, the .blend) does **not** come back.

`restore.sh` now prefers GitHub and falls back to the local mirror.

### After a reset, two commands

```bash
bash tools/setup_env.sh        # reinstalls Blender, no root needed
bash tools/set_token.sh        # re-arms GitHub pushes
```

The token cannot be stored durably inside the sandbox: a reset wipes
`/home/user/.git-credentials` and the global git config, and the only files
that survive are tracked ones — where a token must never go. Re-running
`set_token.sh` is the deliberate trade-off.

### Credential safety

`.snapshot-remote` is committed, so `snapshot.sh` strips any `user:pass@` from
the remote URL before writing it. Verified with a dummy token: the file stayed
clean and the string never entered history. The real token lives only in
`/home/user/.git-credentials`, mode 600, outside the workspace and gitignored.


