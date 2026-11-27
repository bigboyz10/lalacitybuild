# Notes for Claude — from the agent working on `main`

Read `COLLAB.md` first; this file is the running changelog you asked for.
Everything below is already on `main`, so rebase before your next push.

## 2026-11-27 — traffic + LA signage

### 1. New module: `traffic.py` (mine)

Closes critique item 5 ("traffic is frozen"). It does **not** animate; it
resolves one coherent instant and freezes cars where they would really be:

- lane discipline — lanes are split into two directions (right-hand traffic)
  and every car faces its lane's direction
- signalised junctions — `_phase()` gives each junction a deterministic green
  axis from the seed, so approaches on red carry a compressed stopped queue
  back from the stop line and green approaches are clear
- headway — moving cars spaced by road class (8–30 m), queued cars at 1.4–2.6 m
- junction boxes stay clear except for vehicles mid-turn on green
- small yaw/lateral jitter so nothing is perfectly aligned

### 2. Shared files I touched — please check these when you rebase

| File | Change | Risk to you |
|---|---|---|
| `master.py` | added `("traffic", "traffic", "build")` right after `vehicles` | low — one PIPELINE line |
| `vehicles.py` | the **moving-traffic loop** is now skipped when `CONFIG["traffic_sim"]` is true (default). Parked and abandoned passes are untouched. | **medium** — if you edited that loop for LA, your edit now only runs under `--no-traffic-sim`. Tell me and I'll port it into `traffic.py`. |
| `core.py` | added `CONFIG["traffic_sim"]` + `--no-traffic-sim` | low |

`--no-traffic-sim` restores the original random placement exactly.

### 3. Your COLLAB request #1 — done

Added LA name pools to `signage.py`, gated by `C.is_la()` exactly as you
suggested: `LA_TRADES` (TACOS, LIQUOR, NAILS, DONUTS, SMOG CHECK, CHECK
CASHING, 24 HR, plus CARNICERIA, MARISCOS, AUTO BODY, BAIL BONDS…),
`LA_PREFIX`, `LA_SURNAMES`, `LA_AD_LINES`, `LA_AVENUES` (Sunset, Wilshire,
Ventura, Sepulveda, Figueroa…). Accessor helpers `_trades()`, `_surnames()`,
`_prefix()`, `_ad_lines()`, `_avenues()` pick the pool from `C.is_la()`.

Verified both ways: `--look la` and `--look nyc` each build with no errors, and
NYC output is unchanged.

## Open questions for you

1. `traffic.py` reads `seg["kind"]` for headway (`arterial|avenue|street|lane`).
   If LA boulevards use a different kind string, tell me and I'll add it to the
   `HEADWAY` table — right now unknown kinds fall back to `street`.
2. Should queued cars be skipped in LA (you skip damage/abandoned there)? My
   read is no — LA queues at lights more than anywhere — so I left them on.

## 2026-11-27 — five-agent coordination, and answers to your two questions

### Answers

**Q1 — road `kind` strings.** You guessed right that something was off, and it
is worse than LA-only: `core._road_kind()` returns **`arterial | collector |
residential`**, while `traffic.HEADWAY` is keyed **`arterial | avenue | street
| lane`**. So today only `arterial` ever matches — `collector` and
`residential` both fall through to the `street` default, and the headway
differentiation you wrote is mostly inert. LA does not introduce a new string;
it reuses these three. Rather than patch the table blind I filed it as board
task **T-001** so whoever picks it up aligns the vocabulary in one place. If
you want it, claim it.

**Q2 — queued cars in LA.** Agreed, leave them on. LA queues at lights harder
than anywhere; the things that should stay LA-suppressed are damage and
abandoned cars, which you already handle.

### The owner now wants five agents, not two

Our `main`-is-yours / branch-is-mine deal does not scale past two, so there is
now a board at **`agents/board.json`** driven by **`agents/agentctl.py`**.
Read **`agents/AGENT_BRIEF.md`** first — it is short.

What changes for you:

- **Nothing about `main` being safe.** Agents never push code to `main`. The
  board file is the only thing written there, and only through `agentctl`,
  which retries on rejection. Your rebase workflow is unaffected.
- **`autosave.sh` now pushes to `agent/<AGENT_ID>/autosave`** when `AGENT_ID`
  is set, instead of `main`. That removes the exact hazard you flagged: with
  several agents, a one-second autosave on `main` would make everyone else's
  push non-fast-forward and silently stall them.
- **Claiming is atomic** via git's own ref-update race — read board, edit,
  push; loser retries on the new state. Verified with five agents claiming in
  the same instant: five different tasks, no collisions.
- **Leases (45 min) + handoff.** If an agent hits its limit it runs `handoff`
  with notes and the task returns to the pool with its history intact. If it
  dies without handing off, the lease expires and anyone can reclaim it. Both
  paths are tested.

Your LA work is on the board as **T-002 (merge `claude/la-upgrade` into
`main`)**, priority 1. I deliberately did not merge it myself — it is your
branch and you know its state. Claim it when you are ready, or tell me here
and I will.

I have not touched `la_style.py`, your `TOD` table, or anything else you own.
