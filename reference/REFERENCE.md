# REFERENCE — the LA look, in three pictures

> **For every agent.** The owner asked for real-life reference images of how this
> map should read, and for all of us to grade our work against them. These are
> **AI-generated look targets** (photoreal intent, *not* photographs) committed so
> everyone shares one visual north star. Open them, then match your module to them.

| File | What it shows | Use it to grade |
|---|---|---|
| `reference/la_golden_boulevard.jpg` | street-level, golden hour, wide boulevard | `lighting.py` golden TOD, `la_style.py` palms + strip-mall pylon, `roads.py`/`sidewalks.py`, `signage.py`, `props.py` poles/wires |
| `reference/la_residential_day.jpg` | residential side street, harsh midday | `buildings_types.py` bungalow/duplex, `roofs.py` terracotta, `vegetation.py` dry parkways, `sidewalks.py`, `vehicles.py` |
| `reference/la_aerial_golden.jpg` | helicopter aerial, golden hour | `core.py` plan/block scale, `la_style.py` backdrop + haze, `render_export.py` grade, downtown cluster |

## What the pictures say (read off the images)

**Light & air**
- Golden hour = low amber sun, *long* raking shadows, pale warm sky graded to a
  hazy horizon. `lighting.TOD["golden"]` (elev ~10°, warm color) is the target.
- Midday = deep blue clear sky, hard short shadows, strong warm bounce off stucco.
- Distance always softens into warm smog; the San Gabriels read blue-brown, never
  crisp. `la_style._tint_mountain` distance blend is the target.

**Ground plane**
- Asphalt is **light, sun-bleached gray** with faded yellow paint — not black.
- Sidewalks are **smooth scored concrete slabs** with expansion joints, *not*
  pavers. (Fixed in T-016: LA `sidewalk`/`pavement` now bind the smooth `concrete`
  set.)
- Parkway strips between curb and walk are **dry tan/brown grass**, not green.

**Buildings**
- 1–3 story sun-bleached stucco: cream, peach, sage, pale blue, butter. Flat tar
  roofs on most; terracotta barrel tile on the Spanish bungalows/duplexes.
- Stucco has fine photographic grain under the palette hue (T-015 bindings).

**Palms**
- Tall skinny Washingtonia with the shaggy tan dead-frond skirt; fronds are
  **olive / yellow-green**, not deep green. Fat Canary Island date palms mixed in.

**Street furniture**
- Strip malls front a surface lot with a **tall multi-tenant pylon sign**
  (LIQUOR / MARKET / NAILS panels stacked), not a single blank box.
- Wooden utility poles with **sagging black wires** crossing the street.
- Chainlink fences, some with green privacy screen; low wrought-iron on bungalows.

## Already matching (don't redo)
- Palms, mountain backdrop + haze, wide boulevards, stucco/terracotta PBR,
  golden/day/night TOD, scored-slab sidewalks (T-016).

## Open targets → board T-017 (build-capable agent, verify against the images)
1. `render_export.py`: subtle warm color-balance + faint glare at golden hour.
2. `vegetation.py` / grass material: dry-tan parkway tint in LA (`C.is_la()`).
3. `core.PALETTE["palm_frond"]`: nudge hue toward olive-yellow (LA-only entry).
4. `la_style.strip_mall` / `signage.py`: stacked multi-tenant pylon panels.
5. `props.py`: catenary/sagging wires between existing electricity poles.
6. `assets_pbr.py`: optional sun-bleach albedo lift on `asphalt_la` (agent-opus-la
   area — ping me before editing).

## How to use
Render `blender -b -P master.py -- --size 320 --look la --time golden`, open the
matching reference beside it, and close the biggest gap first. Note what you
matched in `collab/FROM_OTHER_AI.md`.

— agent-opus-la (T-016)
