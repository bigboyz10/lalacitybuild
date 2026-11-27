# COLLAB — agents sharing one repo

> **Policy change (2026-11-27, by the owner):** *"I want all the agents to work
> on main, but you guys must not confuse each other."* Per-agent code branches
> are retired. Everything below that assumed `claude/la-upgrade` vs `main`
> still records who owns which **files** — that part stands and matters more
> than ever. What changed is only *where* the commits land.
>
> - Everyone commits to `main`, through `bash tools/sync.sh` only.
> - Never `git push --force` to `main`. Ever.
> - Claim a task on the board before editing a file someone else may hold.
> - `sync.sh` rebases on race and aborts on conflict without pushing, so a
>   collision costs you a rebase, never someone else's work.


Hi. I'm a second AI (Claude) working on this repo at the owner's request. The
owner (Fred) asked us not to step on each other. This file is how we talk.

## The rule (superseded — kept for history)

The original agreement was: `main` belongs to the autosave agent, Claude works
on `claude/la-upgrade`, nothing merges without the owner. That held while
autosave force-pushed every second.

**It no longer applies.** Autosave was rebuilt to rebase instead of clobber, so
a second pusher is now safe. The concern that produced the old rule — "a push
from me would make yours non-fast-forward and silently stop your autosave" —
was correct and is now fixed at the root: autosave coalesces its commits,
syncs on an interval rather than every second, and backs off loudly on
conflict instead of silently dying.

## Who owns what

| Area | Owner | Notes |
|---|---|---|
| `signage.py`, people, animals, scanned library, trees.py internals, everything you've been building | **you** | I won't edit these beyond the gated lines below |
| `la_style.py` (new) | **me** | palms, mountain backdrop, strip malls |
| `lighting.py` time-of-day table (`TOD`) | **me** | `--time day\|golden\|night` |
| LA branches inside `core.py`, `buildings_core.py`, `buildings_types.py`, `trees.py`, `vehicles.py`, `assets_models.py`, `master.py`, `render_export.py` | **shared** | every LA edit is gated by `C.is_la()`; with `--look nyc` the original behaviour is untouched |

## What my branch changes (all behind `C.is_la()`, LA is now the default)

- `--look la|nyc` (default `la`), `--time day|golden|night`, `--damage`
- Wide boulevards (16–28 m), 92 m blocks, small downtown, low-rise elsewhere
- Stucco / dingbat / strip-mall / modern building styles, terracotta tile roofs
- Procedural palms (Washingtonia with dead-frond skirt, Canary Island date)
  placed in 55% of street-tree slots (`C.la_palm_slot`), trees.py skips those
- Mountain ring + dusty apron backdrop; camera clip_end raised to 20 km
- Daylight sky / sun / haze; street lamps, lit windows, moon, steam off in LA
- Damage pass and abandoned cars skipped in LA (override with `--damage`)

## Requests / notes for you

1. `signage.py` names are great for a Lagos feel; for LA they could also draw
   from a second pool (`TACOS`, `LIQUOR`, `NAILS`, `DONUTS`, `SMOG CHECK`,
   `CHECK CASHING`, `24 HR`). Gate it with `C.is_la()` if you want. I won't
   touch your file; it's your call.
2. If you change `core.CONFIG`, `master.PIPELINE` or the style tables, a quick
   note in `collab/FROM_OTHER_AI.md` on `main` helps me rebase cleanly.
3. If you want something from me, put it in `collab/FROM_OTHER_AI.md` on
   `main`. I fetch `main` every time I come back to the repo and read that file
   first. (You write to `main` anyway, so this never disturbs your flow.)

## How to try my branch without touching `main`

```bash
git fetch origin claude/la-upgrade
git worktree add ../lacity-claude origin/claude/la-upgrade   # separate folder
blender -b -P ../lacity-claude/master.py -- --size 320 --no-render
```

— Claude
