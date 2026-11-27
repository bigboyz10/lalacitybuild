# Agent brief — read this first

You are one of up to five AI agents working on **lalacitybuild**, a procedural
city generator for Blender 4.x. You cannot see the other agents. The GitHub
remote is the only thing you share, so all coordination happens through it.

## 60-second orientation

```bash
bash tools/setup_env.sh && source tools/env.sh   # Blender, no root needed
python3 agents/agentctl.py status                # what everyone is doing
python3 agents/agentctl.py claim                 # take the top free task
```

Then build something small to prove the toolchain works:

```bash
blender -b -P master.py -- --size 200 --no-render
```

## The three rules

1. **Everyone commits to `main`.** The owner asked for a single shared branch,
   so there are no per-agent code branches any more. You push to `main` like
   everyone else — but only ever through `bash tools/sync.sh`, never with a
   bare `git push`, and **never** with `--force`.
2. **Claim before you touch anything.** The board is what stops two agents
   editing the same file at the same second. A rebase can merge edits to
   different files automatically; it cannot merge two rewrites of the same
   function.
3. **Commit small and sync often.** On a shared branch the cost of a conflict
   scales with how long you sat on your changes. Minutes, not hours.

## Working on a shared main

```bash
bash tools/sync.sh "T-00X: what you changed"
```

`sync.sh` commits, fetches, rebases your work on top of whatever arrived while
you were busy, and pushes. If two agents push at the same instant git rejects
the loser as non-fast-forward — never a silent overwrite — and the script
rebases and retries with a jittered backoff. Verified with two agents pushing
simultaneously: both edits ended up on `main`, in a linear history.

If your change genuinely collides with someone else's, `sync.sh` **aborts and
pushes nothing**, names the conflicting files, and leaves your tree and your
commit exactly as they were:

```
[sync beta] CONFLICT with another agent in: shared_file.txt
[sync beta] nothing was pushed and your tree is untouched.
[sync beta] resolve with:  git fetch origin && git rebase origin/main
```

Resolve it deliberately, then run `sync.sh` again. Never "fix" it by forcing.

## Why claiming is safe

`agentctl` reads the board from the remote, edits it, and pushes. Git ref
updates are atomic, so if two agents claim at the same moment one push is
rejected as non-fast-forward; the loser re-reads the new board and retries.
Exactly one agent ends up owning a task. Board edits happen in a private clone
at `~/.agent-board`, so your working tree is never disturbed.

## Leases and handoff — the part that matters when you hit a limit

A claim carries a **45 minute lease**. While you work:

```bash
python3 agents/agentctl.py heartbeat         # extends the lease
python3 agents/agentctl.py note T-003 "wired the jitter into emit_building"
```

Write notes as you go. They are the handoff record.

**When you are about to run out of context, budget or time:**

```bash
bash tools/sync.sh "T-003 WIP: jitter works for brick"   # land the partial work
python3 agents/agentctl.py handoff T-003 "60% done: jitter works for brick,
  plaster still uniform; continue in emit_building()"
```

Partial work on a shared branch must still *build*. If it does not, keep it
local and hand off with a note saying so rather than breaking `main` for
everyone.

The task returns to `todo` with every note intact, and your commits are
already on `main`. The next agent reads the notes and continues from where you
stopped rather than starting over.

**If you vanish without handing off,** the lease simply expires. Any agent can
then run `release-stale` and reclaim the task; whatever you synced is already
on `main`, and your notes explain where you got to.

## Finishing

```bash
bash tools/sync.sh "T-003: per-building window jitter"
python3 agents/agentctl.py done T-003 "landed on main: both looks build clean"
```

Your code is already on `main`, so `done` marks the task `review` for a second
pair of eyes rather than gating a merge.

## Picking work when several agents are online

`claim` hands out the highest-priority ready task, skipping anything whose
`depends_on` is unfinished. To stay in your lane:

```bash
python3 agents/agentctl.py claim --area trees.py
python3 agents/agentctl.py claim --size S        # small task, short session
```

Tasks list the files they touch in `area`. Two agents holding tasks that name
the same file should talk through `collab/FROM_OTHER_AI.md` before either
starts editing.

## Talking to each other

- `collab/FROM_OTHER_AI.md` — running changelog and questions, on `main`.
- `COLLAB.md` — standing ownership agreements.
- Task `notes` — everything specific to one piece of work.

## Project facts worth knowing

- `master.py` runs modules in `PIPELINE` order; each module is also runnable
  standalone with `blender -b -P <module>.py`.
- Everything is metric and real-scale: 3.0 m lanes, 3.4 m floors, 1.7 m eye.
- `--look la|nyc` switches the city style; LA edits are gated by `C.is_la()`.
- Rendering uses Cycles on CPU headless; EEVEE needs a GPU and crawls here.
- A sandbox reset wipes everything outside the workspace, Blender included.
  `tools/setup_env.sh` rebuilds it, `tools/set_token.sh` re-arms pushes; only
  tracked files survive, so sync before you stop.
- The self-critique at the end of a master run lists the remaining realism
  gaps. Most open board tasks come straight from it.
