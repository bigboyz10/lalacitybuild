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

1. **Never push code to `main`.** Your work goes on the branch the board gives
   you: `agent/<your-id>/<task-id>`. `main` is shared ground.
2. **The board is the only file you write on `main`,** and only through
   `agentctl.py`, which handles the race.
3. **Claim before you touch anything.** If it is not claimed by you, another
   agent may already be mid-edit in the same file.

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
git push origin HEAD:agent/<your-id>/t-003   # push the partial work first
python3 agents/agentctl.py handoff T-003 "60% done: jitter works for brick,
  plaster still uniform; see branch agent/me/t-003, continue in emit_building()"
```

The task returns to `todo` with every note intact, and the branch stays on the
remote. The next agent reads the notes, checks out the branch, and continues
from where you stopped rather than starting over.

**If you vanish without handing off,** the lease simply expires. Any agent can
then run `release-stale` and reclaim the task; your pushed branch is still
there, and your notes explain where you got to.

## Finishing

```bash
git push origin HEAD:agent/<your-id>/<task-id>
python3 agents/agentctl.py done T-003 "ready for merge: both looks build clean"
```

That marks it `review`. A human or a designated merge agent merges to `main`
and runs `done --merged`.

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
  `tools/setup_env.sh` rebuilds it; only tracked files survive.
- The self-critique at the end of a master run lists the remaining realism
  gaps. Most open board tasks come straight from it.
