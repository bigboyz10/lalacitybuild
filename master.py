# =============================================================================
#  CITY BUILD  --  MASTER
#  blender -b -P master.py -- [--seed N] [--size M] [--density D]
#                              [--quality preview|high] [--render] [--export]
#                              [--only module1,module2] [--no-lod]
#
#  Builds the entire city in dependency order, then renders the four test
#  frames and/or exports city.glb, and prints the per-collection report.
# =============================================================================
import bpy
import os
import sys
import time
import importlib

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C

# (config key, module name, builder attribute)
PIPELINE = [
    ("terrain",    "terrain",          "build"),
    ("roads",      "roads",            "build"),
    ("sidewalks",  "sidewalks",        "build"),
    ("buildings",  "buildings_types",  "build"),
    ("facade",     "facade_detail",    "build"),
    ("roofs",      "roofs",            "build"),
    ("damage",     "damage",           "build"),
    ("props",      "props",            "build"),
    ("utilities",  "utilities",        "build"),
    ("vehicles",   "vehicles",         "build"),
    ("vegetation", "vegetation",       "build"),
    ("trees",      "trees",            "build"),
    ("story",      "story",            "build"),
    ("signage",    "signage",          "build"),
    ("models",     "assets_models",    "build"),
    ("people",     "people",           "build"),
    ("animals",    "animals",          "build"),
    ("lighting",   "lighting",         "build"),
    ("enhance",    "enhance",          "build"),
]

CRITIQUE = """
==============================================================================
 SELF-CRITIQUE  --  what is missing / what still looks fake
==============================================================================
 CLOSED in later passes:
   x Facade rhythm   -- per-building window jitter, floor bands, blank party
                        walls and skipped openings (buildings_core).
   x Interior depth  -- glass is recessed into a lined reveal with a dark room
                        volume and furniture slabs behind it.
   x Ground floor    -- frontages split into separate tenancies with their own
                        bay module, sill height, awning depth and fascia.
   x Signage         -- extruded readable type on blades, billboards, street
                        plates and door numbers (signage).
   x Vegetation      -- grown branching trees, 17 variants (trees), plus CC0
                        photoscanned grass, weeds and ferns (assets_models).
   x People          -- proportioned figures in five poses (people).
   x Animals         -- birds, dogs, pigeons and rats (animals).

 STILL OPEN:
 1. Traffic is frozen. Cars are placed, not simulated, so there is no
    queueing at lights and no lane discipline.
 2. No construction sequencing. Cranes exist but there are no half-built
    floors, formwork or material lay-down areas.
 3. Puddles are flat discs and do not reflect the sky.
 4. The elevated highway has no ramps, no signage gantries and no
    expansion-joint noise.
 5. Interiors are a single dark volume. There is no per-room lighting
    variation behind the glass at night beyond the lit-window pass.
 6. Street trees still repeat their 17 silhouettes on long avenues; a
    species-per-street rule would read better.
==============================================================================



def run():
    t0 = time.time()
    C.bootstrap(banner="CITY BUILD  MASTER")
    C.build_all_materials()

    # photographic PBR upgrade (no-op when nothing has been downloaded)
    if C.CONFIG.get("textures", True):
        try:
            import assets_pbr
            assets_pbr.build()
        except Exception as exc:
            print("  !! texture upgrade failed: {}".format(exc))

    only = C.CONFIG["only"]
    for key, mod_name, fn_name in PIPELINE:
        if only and key not in only:
            continue
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            print("  !! import failed for {}: {}".format(mod_name, exc))
            continue
        fn = getattr(mod, fn_name, None)
        if fn is None:
            print("  !! {} has no {}()".format(mod_name, fn_name))
            continue
        t = time.time()
        print("  -> {}".format(key))
        try:
            fn()
        except Exception as exc:
            import traceback
            print("  !! {} failed: {}".format(key, exc))
            traceback.print_exc()
        print("     {:.1f}s".format(time.time() - t))

    # cameras / render / export
    if not only or "render" in only:
        try:
            import render_export
            render_export.build()
        except Exception as exc:
            print("  !! render/export failed: {}".format(exc))

    if C.CONFIG.get("save_blend", True):
        try:
            C.save_blend()
        except Exception as exc:
            print("  !! saving .blend failed: {}".format(exc))

    print(CRITIQUE)
    data = C.report()
    print("  total build time: {:.1f}s".format(time.time() - t0))
    print("  objects: {}   triangles: {:,}".format(
        data["objects"], data["triangles"]))
    return data


if __name__ == "__main__":
    run()