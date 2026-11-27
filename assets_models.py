# =============================================================================
#  CITY BUILD  --  M17 : SCANNED ASSET LIBRARY
#  Loads the baked CC0 photoscan library from assets/lib/*.glb and places it
#  through the city: real trees along streets and in parks, shrubs, ferns,
#  flowers, grass and weeds on every verge, boulders and rocks on the
#  landscape, street furniture on sidewalks, clutter in industrial lots and
#  alleys, AC units on roofs.
#
#  The library is produced by tools/build_library.py from the raw Poly Haven
#  downloads; only the compact baked .glb files are committed, so this module
#  works straight from a fresh clone.
#
#  standalone:  blender -b -P assets_models.py
# =============================================================================
import glob
import math
import os
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "tools"))

import core as C
from core import CONFIG, U, rng, plan_city

try:
    from catalog import MODELS, by_tag
except Exception:
    MODELS, by_tag = {}, lambda t: []

LIB_DIR = os.path.join(_HERE, "assets", "lib")
BASE_Z = 0.15

_SRC = {}


def available():
    return os.path.isdir(LIB_DIR) and bool(glob.glob(os.path.join(LIB_DIR, "*.glb")))


def have(key):
    return os.path.exists(os.path.join(LIB_DIR, key + ".glb"))


def tag(name):
    """Catalog keys with this tag that are actually present in the library."""
    return [k for k in by_tag(name) if have(k)]


def _load(key):
    """Import a baked asset once; return a hidden source object."""
    if key in _SRC:
        return _SRC[key]
    path = os.path.join(LIB_DIR, key + ".glb")
    if not os.path.exists(path):
        _SRC[key] = None
        return None

    before = {o.name for o in bpy.data.objects}
    try:
        bpy.ops.import_scene.gltf(filepath=path)
    except Exception as exc:
        print("    !! load {} -> {}".format(key, exc))
        _SRC[key] = None
        return None

    new = [n for n in (o.name for o in bpy.data.objects) if n not in before]
    mesh_names = [n for n in new
                  if bpy.data.objects.get(n) and bpy.data.objects[n].type == "MESH"]
    if not mesh_names:
        _SRC[key] = None
        return None

    src_name = mesh_names[0]
    if len(mesh_names) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for n in mesh_names:
            ob = bpy.data.objects.get(n)
            if ob:
                ob.select_set(True)
        bpy.context.view_layer.objects.active = bpy.data.objects[src_name]
        try:
            bpy.ops.object.join()
        except Exception:
            pass
        act = bpy.context.view_layer.objects.active
        src_name = act.name if act else src_name

    src = bpy.data.objects.get(src_name)
    if src is None:
        _SRC[key] = None
        return None

    for n in new:
        ob = bpy.data.objects.get(n)
        if ob is not None and ob.name != src_name and ob.type == "EMPTY":
            try:
                bpy.data.objects.remove(ob, do_unlink=True)
            except Exception:
                pass

    src.name = "SRC_" + key
    src.hide_render = True
    src.hide_viewport = True
    for c in list(src.users_collection):
        c.objects.unlink(src)
    C.col("CITY_Lib_src").objects.link(src)
    _SRC[key] = src
    return src


def place(key, name, collection, loc, rot=0.0, scale=1.0, tilt=0.0):
    src = _load(key)
    if src is None:
        return None
    ob = bpy.data.objects.new(name, src.data)
    ob.location = loc
    ob.rotation_euler = (tilt, 0.0, rot)
    base = src.scale.x * scale
    ob.scale = (base, base, base)
    C.link_object(ob, collection)
    return ob


def build():
    if not available():
        print("  no baked library - run tools/fetch_models.py then tools/build_library.py")
        return 0

    R = rng("library")
    plan = plan_city()
    half = plan["half"]
    col = C.col("CITY_Library")
    density = CONFIG.get("density", 0.8)
    sw = U["sidewalk"]
    n = [0]

    trees = tag("tree") or []
    saplings = [k for k in trees if "sapling" in k or "stump" in k]
    big_trees = [k for k in trees if k not in saplings and "dead" not in k]
    shrubs = tag("shrub")
    grass = tag("grass")
    weeds = tag("weed")
    flowers = tag("flower")
    ground = tag("ground")
    rocks = tag("rock")
    street = tag("street")
    clutter = tag("clutter")
    debris = tag("debris")
    roofkit = tag("roof")
    if C.is_la():
        # no wilderness trees, stumps or dead trunks on LA boulevards;
        # palms and shade trees are grown procedurally instead
        saplings, big_trees = [], []

    def put(keys, x, y, z=BASE_Z, scale=1.0, spread=0.0, tilt=0.0):
        if not keys or abs(x) > half or abs(y) > half:
            return
        if spread:
            x += R.uniform(-spread, spread)
            y += R.uniform(-spread, spread)
        key = R.choice(keys)
        s = scale * R.uniform(0.82, 1.22)
        if place(key, "{}_{:05d}".format(key, n[0]), col,
                 (x, y, z), R.uniform(0, math.tau), s, tilt):
            n[0] += 1

    # ---- street trees: regular spacing along every block edge -----------
    for blk in plan["blocks"]:
        cx, cy, bw, bh = blk["cx"], blk["cy"], blk["w"], blk["h"]
        district = blk.get("district", "midtown")
        if district == "industrial":
            spacing = 22.0
        elif district == "downtown":
            spacing = 14.0
        else:
            spacing = 11.0

        for edge in range(4):
            length = bw if edge < 2 else bh
            count = max(0, int(length / spacing))
            for i in range(count):
                t = (i + 0.5) / max(1, count) - 0.5
                off = sw * 0.55
                if edge == 0:
                    x, y = cx + bw * t, cy - bh * 0.5 - off
                elif edge == 1:
                    x, y = cx + bw * t, cy + bh * 0.5 + off
                elif edge == 2:
                    x, y = cx - bw * 0.5 - off, cy + bh * t
                else:
                    x, y = cx + bw * 0.5 + off, cy + bh * t
                if R.random() < 0.80:
                    put(big_trees or saplings, x, y, spread=0.5,
                        scale=R.uniform(0.80, 1.25))
                    # tree-pit ground cover
                    for _ in range(R.randint(1, 3)):
                        put(grass + weeds + ground, x, y, spread=1.0, scale=0.9)

        # verge planting
        for _ in range(int(R.uniform(5, 13) * density)):
            edge = R.randint(0, 3)
            t = R.uniform(-0.48, 0.48)
            if edge in (0, 1):
                x = cx + bw * t
                y = cy + (bh * 0.5 + sw * 0.8) * (1 if edge else -1)
            else:
                y = cy + bh * t
                x = cx + (bw * 0.5 + sw * 0.8) * (1 if edge == 3 else -1)
            put(grass + weeds + flowers, x, y, spread=0.7, scale=R.uniform(0.7, 1.4))

        # street furniture
        for _ in range(int(R.uniform(1, 4) * density)):
            edge = R.randint(0, 3)
            t = R.uniform(-0.42, 0.42)
            if edge in (0, 1):
                x = cx + bw * t
                y = cy + (bh * 0.5 + sw * 0.5) * (1 if edge else -1)
            else:
                y = cy + bh * t
                x = cx + (bw * 0.5 + sw * 0.5) * (1 if edge == 3 else -1)
            put(street, x, y)

        if district == "industrial":
            for _ in range(int(R.uniform(2, 6) * density)):
                put(clutter, cx + R.uniform(-bw * 0.4, bw * 0.4),
                    cy + R.uniform(-bh * 0.4, bh * 0.4))

    # ---- parks: dense mixed planting -------------------------------------
    for park in plan.get("parks", []):
        px, py = park.get("cx", 0.0), park.get("cy", 0.0)
        pw, ph = park.get("w", 40.0), park.get("h", 40.0)
        for _ in range(int(16 * density)):
            put(big_trees, px + R.uniform(-pw * 0.44, pw * 0.44),
                py + R.uniform(-ph * 0.44, ph * 0.44),
                scale=R.uniform(0.9, 1.5))
        for _ in range(int(26 * density)):
            put(shrubs, px + R.uniform(-pw * 0.46, pw * 0.46),
                py + R.uniform(-ph * 0.46, ph * 0.46))
        for _ in range(int(150 * density)):
            put(grass + ground + flowers + weeds,
                px + R.uniform(-pw * 0.47, pw * 0.47),
                py + R.uniform(-ph * 0.47, ph * 0.47),
                scale=R.uniform(0.8, 1.6))
        for _ in range(int(9 * density)):
            put(rocks + debris, px + R.uniform(-pw * 0.4, pw * 0.4),
                py + R.uniform(-ph * 0.4, ph * 0.4))

    # ---- riverbank / city edge: rocks and rough vegetation ---------------
    water_y = plan.get("water_y", -half)
    for _ in range(int(60 * density)):
        x = R.uniform(-half, half)
        y = water_y + R.uniform(1.0, 14.0)
        put(rocks, x, y, scale=R.uniform(0.7, 1.6))
    for _ in range(int(80 * density)):
        x = R.uniform(-half, half)
        y = water_y + R.uniform(2.0, 20.0)
        put(grass + weeds + shrubs, x, y, scale=R.uniform(0.8, 1.5))

    # ---- weeds in pavement cracks everywhere -----------------------------
    for _ in range(int(120 * density)):
        put(weeds + grass, R.uniform(-half, half), R.uniform(-half, half),
            scale=R.uniform(0.5, 1.0))

    # ---- rooftop plant --------------------------------------------------
    for ob in [o for o in bpy.data.objects if o.name.startswith("RoofDeck")]:
        if R.random() > 0.35:
            continue
        put(roofkit or street, ob.location.x + R.uniform(-2.5, 2.5),
            ob.location.y + R.uniform(-2.5, 2.5), z=ob.location.z + 0.3)

    print("  library: {} instances from {} sources".format(
        n[0], len([v for v in _SRC.values() if v])))
    return n[0]


if __name__ == "__main__":
    C.bootstrap(banner="M17 SCANNED LIBRARY")
    C.build_all_materials()
    build()
    C.report()
