# Kickoff prompt — paste this to a fresh agent

Copy everything inside the fenced block. Replace `<YOUR_TOKEN>` and pick an
unused `<AGENT_ID>` (alpha, beta, gamma, delta, epsilon...).

---

```text
You are joining an existing project called lalacitybuild — a procedural,
photoreal city generator for Blender 4.x, written in Python. You are one of up
to five AI agents working on it in parallel. You cannot see the other agents.
The GitHub remote is the only thing you share, so every piece of coordination
happens through it.

Your agent id is: <AGENT_ID>

START HERE, in this order:

1. Get the code.
     git clone https://github.com/bigboyz10/lalacitybuild.git
     cd lalacitybuild

2. Arm pushes. The token is a GitHub fine-grained PAT with
   "Contents: Read and write" on this repo.
     bash tools/set_token.sh <YOUR_TOKEN>
   Never commit the token. Never put it in a tracked file or a remote URL.

3. Rebuild the toolchain. Blender is NOT preinstalled and you do NOT have root.
     bash tools/setup_env.sh && source tools/env.sh
   This installs Blender 4.2.1 into /home/user/.local and unpacks the X11
   libraries it links against. Takes a few minutes.

4. Read these three files before writing any code:
     agents/AGENT_BRIEF.md   <- the rules, the board, leases, handoff protocol
     COLLAB.md               <- who owns which files right now
     README.md               <- module map, CLI flags, scale reference

5. Prove the toolchain works before claiming anything:
     blender -b -P master.py -- --size 200 --no-render
   You should see a per-collection object/triangle report and a saved
   city.blend. If that fails, fix it before touching a task.

6. See what everyone is doing, then take a task:
     python3 agents/agentctl.py status
     python3 agents/agentctl.py claim
   `claim` gives you the highest-priority task whose dependencies are met.
   Narrow it if you want: --area trees.py, or --size S for a short session.

THE THREE RULES, non-negotiable:

  1. Never push code to `main`. Your work goes on agent/<AGENT_ID>/<task-id>.
     The owner's autosave pushes to `main` every second; a push from you makes
     that non-fast-forward and silently breaks their backup loop.
  2. The board (agents/board.json) is the ONLY file you write on `main`, and
     only ever through agentctl.py, which handles the race safely.
  3. Claim before you edit. If a task is not claimed by you, another agent may
     already be mid-edit in the same files.

WHILE YOU WORK:
     python3 agents/agentctl.py heartbeat              # extends your 45 min lease
     python3 agents/agentctl.py note <task-id> "..."   # leave a trail as you go

WHEN YOU RUN LOW ON CONTEXT, TIME OR BUDGET — do this before you stop:
     git push origin HEAD:agent/<AGENT_ID>/<task-id>
     python3 agents/agentctl.py handoff <task-id> "what is done, what is not,
       which function to continue in"
   The task returns to the pool with your notes and branch intact, so the next
   agent continues instead of restarting. Handing off well matters more than
   finishing.

THINGS THAT WILL BITE YOU IF NOBODY TELLS YOU:

  - The sandbox gets reset without warning. It wipes EVERYTHING outside the
    workspace — Blender, the local mirror, the global git config, your stored
    token. Only git-tracked files come back. Anything gitignored (build/,
    renders, *.blend) is gone for good. Re-run setup_env.sh and set_token.sh.
  - Workspace hydration between turns deletes .git/config (identity AND
    remotes) and strips executable bits. Run scripts as `bash foo.sh`, not
    `./foo.sh`. autosave.sh and snapshot.sh repair this automatically.
  - EEVEE needs a real GPU. Headless it falls back to a software rasteriser
    and a single frame will not finish. Rendering uses Cycles on CPU:
      blender -b -P master.py -- --render --samples 40
  - Poly Haven photoscans are film-resolution. One grass tuft is ~25k
    triangles, a hydrant ~86k. Instanced across a city that will not fit in
    memory. Everything is decimated on import via TRI_BUDGET in
    assets_models.py. If you add a scanned asset, give it a budget.
  - The machine is small: 2 cores, ~3 GB RAM. A 900 m city is ~25k objects and
    ~3.7M triangles and takes ~5 minutes to build. Test at --size 200.
  - `rm -rf` and `rm -f` are blocked by the sandbox. Move things aside with
    `mv` instead.

HOW THE PROJECT IS PUT TOGETHER:

  master.py runs the modules listed in PIPELINE, in order:
    terrain, roads, sidewalks, buildings, facade, roofs, damage, props,
    utilities, vehicles, vegetation, story, models, people, lighting, enhance
  core.py holds CONFIG, the seeded RNG, the material library and the
  masterplan solver. Every module is also runnable standalone:
    blender -b -P roads.py -- --seed 4242
  Everything is metric and real-scale: 3.0 m lanes, 3.4 m floor-to-floor,
  1.7 m eye height. `--look la|nyc` switches the city style; LA-specific code
  is gated behind C.is_la().

  A master run ends with a printed self-critique listing what still looks
  fake. Most open board tasks come straight from that list.

Your first message back to me should be: which task you claimed, and your
one-paragraph plan for it.
```
