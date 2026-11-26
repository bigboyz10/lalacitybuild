# CITY BUILD — procedural realistic city for Blender 4.x

A complete, seeded, headless city generator. One `master.py` plus one module per
build group. Every module is also runnable on its own.

```
blender -b -P master.py -- --quality preview
blender -b -P master.py -- --quality high --render --export
blender -b -P roads.py  -- --seed 4242
```

## Requirements

Blender 4.0 or newer (tested against the 4.x Python API). No add-ons, no
external assets, no image textures — every material is procedural shader nodes.

## Quick start

```bash
# full city, fast EEVEE preview, no render
blender -b -P master.py -- --quality preview

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
| `--size M` | city footprint in metres (default 480) |
| `--density D` | 0..1 fraction of lots that receive buildings (default 0.75) |
| `--quality preview\|high` | EEVEE fast / Cycles + extra detail |
| `--render` | render the four test frames |
| `--no-render` | force rendering off |
| `--export` | write `city.glb` |
| `--only a,b,c` | run only these module keys |
| `--out PATH` | output directory for renders, glb and JSON reports |
| `--no-lod` | disable LOD collection creation |

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