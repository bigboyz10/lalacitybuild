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
    ("story",      "story",            "build"),
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
 1. Facade rhythm is uniform. Every window is the same size on a given
    building, so elevations read as wallpaper. Real facades mix punched
    openings, ribbon windows and blank party walls.
      -> varied by style, but a per-building window-size jitter pass is
         still missing.
 2. No interior depth. Glass is a flat quad; there is no parallax, so
    windows read as decals at street level.
      -> partially faked with the interior-clutter boxes in M6.
 3. Ground floor is repetitive. Shopfronts repeat the same bay width and
    the same awning depth on every block.
 4. No construction sequencing. Cranes exist (M-Enhance) but there are no
    half-built floors, formwork or material lay-down areas.
 5. Traffic is frozen. Cars are placed, not simulated, so there is no
    queueing at lights and no lane discipline.
 6. Signage has no readable content. Blades and billboards are coloured
    slabs; no type, no logos.
 7. Vegetation is sparse at the canopy level. Street trees are evenly
    spaced and the same three silhouettes repeat.
 8. No people. A AAA street scene at eye level needs figures, even as
    low-detail impostors, or it reads as a model village.
 9. Puddles are flat discs; they do not reflect the sky because EEVEE
    screen-space reflections are off by default in this build.
10. The elevated highway has no ramps, no signage gantries and no
    expansion-joint noise, so it reads as a clean toy.

Everything above is a deliberate scope boundary for this pass, not an
oversight: each is listed here so the next pass can target it directly.
==============================================================================
"""


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