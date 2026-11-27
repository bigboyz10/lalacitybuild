# CITY BUILD — procedural realistic city for Blender 4.x

A complete, seeded, headless city generator. One `master.py` plus one module per
build group. Every module is also runnable on its own.

```
blender -b -P master.py -- --quality preview
blender -b -P master.py -- --quality high --render --export
blender -b -P roads.py  -- --seed 4242
```

## Requirements

Blender 4.0 or newer (tested on 4.2.1 LTS). No add-ons required.

Materials are procedural by default. Optionally the build will use real
photographic CC0 PBR textures and an HDRI sky — see *Realistic assets* below.
Nothing breaks if those files are absent; the procedural path is the fallback.

## Quick start

```bash
# full city, build only, writes city.blend
blender -b -P master.py -- --quality preview --no-render

# full city, Cycles, render the 4 test frames, export city.glb
blender -b -P master.py -- --quality high --render --export

# smaller, denser, different seed
blender -b -P master.py -- --size 320 --density 0.9 --seed 99

# rebuild only some modules
blender -b -P master.py -- --only roads,sidewalks,props
```

## CLI flags

| Flag | Meaning |
|---|---|
| `--seed N` | master seed (default 1337); every module derives its own stream from it |
| `--size M` | city footprint in metres (default 900) |
| `--density D` | 0..1 fraction of lots that receive buildings (default 0.85) |
| `--quality preview\|high` | EEVEE fast / Cycles + extra detail |
| `--render` | render the four test frames |
| `--no-render` | force rendering off |
| `--export` | write `city.glb` |
| `--only a,b,c` | run only these module keys |
| `--out PATH` | output directory for renders, glb and JSON reports |
| `--no-lod` | disable LOD collection creation |
| `--blend NAME` | filename for the saved .blend (default `city.blend`) |
| `--no-blend` | skip writing the .blend |
| `--no-textures` | ignore downloaded textures, stay fully procedural |
| `--engine auto\|eevee\|cycles` | renderer override (default `auto`) |
| `--samples N` | Cycles samples for a `--render` pass (default 64) |

## Realistic assets

`tools/fetch_assets.py` downloads 14 CC0 PBR texture sets and an HDRI sky from
Poly Haven into `assets/`:

```bash
python3 tools/fetch_assets.py --res 2k        # ~130 MB at 2k, ~33 MB at 1k
blender -b -P master.py -- --no-render        # picks them up automatically
```

`assets_pbr.py` then rebuilds the material library with box-projected diffuse /
roughness / normal / AO maps and lights the scene from the HDRI. Displacement is
wired in only at `--quality high`. Re-running the downloader is cheap: existing
files are skipped.

## Rendering

EEVEE needs a real GPU. Headless machines fall back to the llvmpipe software
rasteriser, where it is far slower than Cycles, so `--engine auto` switches to
Cycles on CPU whenever a render is actually requested and keeps EEVEE only for
build-only runs. Force either with `--engine eevee` / `--engine cycles`.

## Module map

| Key | File | Builds |
|---|---|---|
| — | `core.py` | CONFIG, seeded RNG, noise, collections, LOD, material library, geometry helpers, masterplan solver, report |
| terrain | `terrain.py` | ground shell, lot slabs, river + quay, elevated highway |
| roads | `roads.py` | carriageways, paint, crosswalks, patches, cracks, potholes, drains, manholes |
| sidewalks | `sidewalks.py` | slabs, curbs, ramps, tactile pads, joints, tree pits, hatches, skylights |
| buildings | `buildings_types.py` | placement + all building types |
| — | `buildings_core.py` | massing, facades, windows, shopfronts, fire escapes, balconies |
| facade | `facade_detail.py` | downspouts, conduit, blinds, laundry, vents, wall lamps |
| roofs | `roofs.py` | decks, bulkheads, HVAC, tanks, antennas, solar, helipads |
| damage | `damage.py` | boarded windows, stains, soot, cracks, spall, rubble |
| props | `props.py` | 27 street-furniture types |
| utilities | `utilities.py` | poles, catenary wires, street lights, signals, cabinets, cell towers |
| vehicles | `vehicles.py` | 16 vehicle types, parked + moving + abandoned |
| vegetation | `vegetation.py` | street/park trees, hedges, weeds, ivy, moss, stumps |
| story | `story.py` | signs, billboards, graffiti, posters, litter, puddles |
| trees | `trees.py` | branching trees grown from botanical rules, 7 species |
| models | `assets_models.py` | places the 64-asset CC0 scan library: trees, shrubs, flowers, rocks, furniture, clutter |
| people | `people.py` | proportioned pedestrians: walking, standing, sitting, leaning, on phones |
| signage | `signage.py` | readable extruded type: shop blades, billboard copy, street plates, door numbers |
| animals | `animals.py` | pigeons, gulls, crows, sparrows, dogs, cats, rats - perched, flocking, in flight |
| lighting | `lighting.py` | physical sky, sun/moon, practicals, lit windows, fog, steam, birds |
| enhance | `enhance.py` | post-critique additions: cranes, food carts, fences, stands, piles |
| render | `render_export.py` | 3 street cameras + 1 aerial, test renders, GLB export |

## Scale

Everything is metric and true to life: 3.0 m lanes, 0.15 m curbs, 2.1 m doors,
3.4 m floor-to-floor, 1.7 m eye height, 3.2 m sidewalks.

## Outputs

Written to `--out` (default: the script folder):

- `city.blend` — the whole city, with all downloaded textures packed in, so the
  file opens standalone on any machine
- `city_plan.json` — solved masterplan (roads, blocks, intersections, districts)
- `city_report.json` — object + triangle counts per collection
- `render_Cam_Street_A.png` … `render_Cam_Aerial.png` (with `--render`)
- `city.glb` (with `--export`)

## Determinism

`seed` feeds a SHA-256 derived stream per module, so changing one module never
reshuffles another. The same seed and flags always produce the same city.

## Notes

- Collections are named `CITY_*`; LOD collections live under `CITY_LOD`.
- Repeated objects (trees, cars, props) use linked duplicates so mesh data is
  shared and the .glb stays small.
- The self-critique printed at the end of a master run lists the known gaps
  (uniform facades, no people, frozen traffic, unreadable signage) that the
  `enhance` module and a future pass are meant to close.

## Scale reference

Measured on a 2-core headless box, Blender 4.2.1:

| `--size` | `--density` | Objects | Triangles | Build time |
|---|---|---|---|---|
| 160 m | 0.6 | 943 | 79,886 | ~1 s |
| 480 m | 0.85 | 6,643 | 882,894 | ~95 s |
| 900 m | 0.85 | 25,715 | 3,682,782 | ~327 s |

900 m is the current default. Larger footprints keep working but memory climbs
roughly linearly with triangle count.

## Environment

A sandbox reset wipes everything outside the workspace, Blender included.
Rebuild the toolchain with no root required:

```bash
bash tools/setup_env.sh && source tools/env.sh
```

## Backups

The workspace autosaves: `autosave.sh` commits every change within a second and
mirrors it outside the workspace. `snapshot.sh` does the same on demand, and
`restore.sh` rebuilds the workspace from the mirror. See `RECOVERY.md`.


## Realism pass

What changed from the original procedural-only build:

- **People** (`people.py`) — the critique's biggest gap. Figures are built to
  real proportions (7.6 heads tall, correct limb ratios) in five poses, with
  randomised skin, hair, top and trouser materials. Fourteen silhouettes are
  linked-duplicated across sidewalks, crossings, benches and bus shelters.
- **Scanned props** (`assets_models.py`) — 22 CC0 photoscans from Poly Haven:
  hydrants, bins, benches, barriers, barrels, AC units, planters, plus grass
  tufts, dandelions, nettles, ferns, bushes, boulders and dead trunks.
- **Vehicles** — sedan, SUV and pickup bodies are now lofted through
  cross-sections rather than stacked boxes, giving a sloped bonnet, raked
  screen, curved roofline and tapered tail, with wheel arches, mirrors,
  headlights and tail lights.
- **Materials** — 17 procedural shaders replaced by photographic PBR with an
  HDRI sky.

### Triangle budgets

Photoscans ship at film resolution — one grass tuft is 24,730 triangles, a
hydrant 86,316. Instanced across a city that does not fit in memory, so every
source is decimated once on import to a per-key budget (`TRI_BUDGET` in
`assets_models.py`). That cut the scanned layer from 9.2M triangles to 420k
with no visible difference at street distance.


<!-- autosave verification -->


## Asset library

`tools/catalog.py` lists 64 CC0 photoscans from Poly Haven - trees, shrubs,
ferns, flowers, grass, weeds, moss, boulders, coastal rocks, street furniture,
fences, poles, floodlights and industrial clutter.

```bash
python3 tools/fetch_models.py      # raw scans -> assets/raw/   (~950 MB, gitignored)
bash    tools/bake_all.sh          # decimate  -> assets/lib/   (22 MB, committed)
```

The raw scans are film resolution: one island tree is 2,085,320 triangles and
the fir is 465 MB. `tools/build_library.py` decimates each to a per-asset
budget, normalises it to a real height, drops it onto z=0 and downscales
embedded textures to 512 px, producing a 22 MB library that is committed. A
fresh clone therefore has every asset without downloading a gigabyte.

Baking runs one Blender process per asset (`tools/bake_all.sh`) because
importing several multi-million-triangle scans in sequence exhausts memory.

## Vendored Blender

`vendor/blender/` holds Blender 4.2.1 as four 90 MB parts (GitHub rejects any
single file over 100 MB). `tools/setup_env.sh` reassembles, verifies the
SHA-256 sums and installs it with no network and no root:

```bash
bash tools/setup_env.sh && source tools/env.sh
```


### Trees

`trees.py` replaces the original sphere-on-a-stick canopies. Branches are grown
recursively from real botanical rules rather than modelled:

- **da Vinci's rule** — parent radius squared equals the sum of child radii
  squared, so limbs taper the way wood actually does
- **Phyllotaxis** — successive children rotate 137.5 degrees around the parent,
  which is what stops a tree reading as a flat candelabra
- **Gravitropism** — thinning shoots bend back toward vertical, so outer twigs
  lift rather than drooping in straight lines
- **Apical dominance** varies by species: a poplar holds one leader, an oak
  forks low and spreads
- **Root flare** — buttress roots at the base, because a trunk meeting the
  ground as a clean cylinder is one of the clearest giveaways of a fake tree

Seven species (street plane, street maple, park oak, poplar, conifer, sapling,
bare winter) at roughly 1,700 triangles each, instanced across the city. Leaves
are crossed quad clusters at the twig tips, so canopies break up against the
sky instead of reading as solid balls.

Street trees land in the pits the sidewalk module cuts, so trunks never punch
through paving. Poly Haven's photoscanned trees were rejected deliberately:
about 500 MB of geometry each, unusable at city scale.


## Signage

`signage.py` closes the last of the original self-critique: signs now carry
real, readable type rather than coloured slabs.

- Shop blades take trade names from a mix of surnames, trades and prefixes
  (`OKONKWO & SONS`, `24H LAUNDROMAT`), set on both faces of the blade.
- Billboards get short ad lines auto-sized to the hoarding width.
- Intersections get street-name plates on poles, numbered east-west and named
  north-south, so the grid reads consistently as you move through it.
- Entrances get door numbers derived from position along the block.

Type is set in Blender's built-in font and **converted to mesh**, so the signs
are real geometry: they survive `.glb` export and need no font installed on
whatever machine opens the file. Each string is auto-shrunk to fit its board.
