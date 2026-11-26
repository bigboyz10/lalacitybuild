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

## Backups

The workspace autosaves: `autosave.sh` commits every change within a second and
mirrors it outside the workspace. `snapshot.sh` does the same on demand, and
`restore.sh` rebuilds the workspace from the mirror. See `RECOVERY.md`.
