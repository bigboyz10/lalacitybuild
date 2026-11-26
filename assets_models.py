# =============================================================================
#  CITY BUILD  --  M17 : SCANNED MODEL LIBRARY
#  Imports the CC0 photoscanned glTF models downloaded by
#  tools/fetch_models.py and scatters them through the city as linked
#  duplicates, so real geometry replaces the crude procedural stand-ins for
#  hydrants, bins, benches, barriers, grass tufts, weeds, ferns and rubble.
#
#  Hero trees are deliberately excluded: Poly Haven's are ~500 MB of geometry
#  each, which a city of thousands of instances cannot carry.  Street trees
#  stay procedural; the ground layer gets real scanned foliage.
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

import core as C
from core import CONFIG, U, rng, plan_city

MODEL_DIR = os.path.join(_HERE, "assets", "models")
BASE_Z = 0.15

# Photoscans arrive at film resolution - a single grass tuft can be 40k
# triangles.  Instanced thousands of times that will not fit in memory, so each
# source is decimated once, on import, to a budget suited to how close the
# camera ever gets to it.
TRI_BUDGET = {
    "grass_tuft": 900, "grass_tuft_2": 900, "grass_bermuda": 700,
    "weed_dandelion": 700, "weed_nettle": 900, "fern": 1200, "bush": 1800,
    "potted_plant": 1800, "boulder": 900, "dead_trunk": 1500,
    "hydrant": 2200, "trash_can": 1800, "bench": 2000, "planter": 1200,
    "road_barrier": 900, "road_barrier_2": 900, "barrel": 900,
    "barrel_rust": 900, "cardboard_box": 500, "trashbag": 900,
    "aircon": 1500, "wet_sign": 700,
}
DEFAULT_BUDGET = 1500

# key -> (target height in metres, upright?)  used to normalise scan scale
NORMALISE = {
    "hydrant": 0.78, "trash_can": 0.95, "bench": 0.86, "road_barrier": 0.82,
    "road_barrier_2": 0.82, "barrel": 0.88, "barrel_rust": 0.88,
    "cardboard_box": 0.42, "trashbag": 0.62, "aircon": 0.70, "planter": 0.55,
    "wet_sign": 0.62, "grass_tuft": 0.28, "grass_tuft_2": 0.32,
    "grass_bermuda": 0.18, "weed_dandelion": 0.24, "weed_nettle": 0.45,
    "fern": 0.50, "bush": 0.85, "potted_plant": 0.65, "boulder": 0.70,
    "dead_trunk": 1.30,
}

_LOADED = {}


def available():
    return os.path.isdir(MODEL_DIR) and bool(os.listdir(MODEL_DIR))


def _import_gltf(key):
    """Import one model once; return a hidden source object to duplicate."""
    if key in _LOADED:
        return _LOADED[key]
    folder = os.path.join(MODEL_DIR, key)
    hits = glob.glob(os.path.join(folder, "*.gltf")) + glob.glob(os.path.join(folder, "*.glb"))
    if not hits:
        _LOADED[key] = None
        return None

    before = {o.name for o in bpy.data.objects}
    try:
        bpy.ops.import_scene.gltf(filepath=hits[0])
    except Exception as exc:
        print("    !! import {} -> {}".format(key, exc))
        _LOADED[key] = None
        return None
    # track by name: join() invalidates the Python references of merged objects
    new_names = [o.name for o in bpy.data.objects if o.name not in before]
    mesh_names = [n for n in new_names
                  if bpy.data.objects.get(n) and bpy.data.objects[n].type == "MESH"]
    if not mesh_names:
        _LOADED[key] = None
        return None

    # join multi-part scans into one object so instancing is cheap
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
        active = bpy.context.view_layer.objects.active
        src_name = active.name if active else src_name

    src = bpy.data.objects.get(src_name)
    if src is None:
        _LOADED[key] = None
        return None

    # drop leftover empties the importer created
    for n in new_names:
        ob = bpy.data.objects.get(n)
        if ob is not None and ob.name != src_name and ob.type == "EMPTY":
            try:
                bpy.data.objects.remove(ob, do_unlink=True)
            except Exception:
                pass

    # decimate to the per-key triangle budget before any instancing happens
    try:
        me = src.data
        tris = sum(len(poly.vertices) - 2 for poly in me.polygons)
        budget = TRI_BUDGET.get(key, DEFAULT_BUDGET)
        if tris > budget * 1.25:
            mod = src.modifiers.new("decimate", "DECIMATE")
            mod.ratio = max(0.01, float(budget) / float(tris))
            bpy.context.view_layer.objects.active = src
            bpy.ops.object.modifier_apply(modifier=mod.name)
            after = sum(len(poly.vertices) - 2 for poly in src.data.polygons)
            print("    {:16s} {:>7,} -> {:>6,} tris".format(key, tris, after))
    except Exception as exc:
        print("    !! decimate {} -> {}".format(key, exc))

    # normalise to a sane real-world height
    target = NORMALISE.get(key)
    if target:
        dims = src.dimensions
        if dims.z > 1e-5:
            s = target / dims.z
            src.scale = (s, s, s)
            bpy.context.view_layer.update()

    src.name = "SRC_" + key
    src.hide_render = True
    src.hide_viewport = True
    for c in list(src.users_collection):
        c.objects.unlink(src)
    C.col("CITY_Models_src").objects.link(src)
    _LOADED[key] = src
    return src


def place(key, name, collection, loc, rot=0.0, scale=1.0):
    src = _import_gltf(key)
    if src is None:
        return None
    ob = bpy.data.objects.new(name, src.data)
    ob.location = loc
    ob.rotation_euler = (0.0, 0.0, rot)
    base = src.scale.x * scale
    ob.scale = (base, base, base)
    C.link_object(ob, collection)
    return ob


def build():
    if not available():
        print("  no downloaded models - run tools/fetch_models.py")
        return 0

    R = rng("models")
    plan = plan_city()
    half = plan["half"]
    col = C.col("CITY_Models")
    density = CONFIG.get("density", 0.8)
    n = 0

    def put(key, x, y, z=BASE_Z, scale=1.0, jitter=True):
        nonlocal n
        if abs(x) > half or abs(y) > half:
            return
        rot = R.uniform(0, math.tau)
        s = scale * (R.uniform(0.85, 1.18) if jitter else 1.0)
        if place(key, "{}_{:04d}".format(key, n), col, (x, y, z), rot, s):
            n += 1

    sw = U["sidewalk"]

    # --- street furniture on sidewalk edges ------------------------------
    for blk in plan["blocks"]:
        cx, cy, bw, bh = blk["cx"], blk["cy"], blk["w"], blk["h"]
        district = blk.get("district", "midtown")

        for _ in range(int(R.uniform(1, 3) * density)):
            edge = R.randint(0, 3)
            t = R.uniform(-0.42, 0.42)
            if edge == 0:
                x, y = cx + bw * t, cy - bh * 0.5 - sw * 0.55
            elif edge == 1:
                x, y = cx + bw * t, cy + bh * 0.5 + sw * 0.55
            elif edge == 2:
                x, y = cx - bw * 0.5 - sw * 0.55, cy + bh * t
            else:
                x, y = cx + bw * 0.5 + sw * 0.55, cy + bh * t
            put(R.choice(["hydrant", "trash_can", "planter", "bench"]), x, y)

        # grass + weeds in tree pits and verges
        for _ in range(int(R.uniform(4, 11) * density)):
            edge = R.randint(0, 3)
            t = R.uniform(-0.48, 0.48)
            if edge in (0, 1):
                x = cx + bw * t
                y = cy + (bh * 0.5 + sw * 0.75) * (1 if edge else -1)
            else:
                y = cy + bh * t
                x = cx + (bw * 0.5 + sw * 0.75) * (1 if edge == 3 else -1)
            put(R.choice(["grass_tuft", "grass_tuft_2", "grass_bermuda",
                          "weed_dandelion", "weed_nettle"]),
                x + R.uniform(-0.5, 0.5), y + R.uniform(-0.5, 0.5),
                scale=R.uniform(0.7, 1.4))

        if district == "industrial":
            for _ in range(int(R.uniform(1, 4) * density)):
                x = cx + R.uniform(-bw * 0.4, bw * 0.4)
                y = cy + R.uniform(-bh * 0.4, bh * 0.4)
                put(R.choice(["barrel", "barrel_rust", "cardboard_box",
                              "road_barrier", "road_barrier_2"]), x, y)

    # --- parks: dense ground foliage -------------------------------------
    for park in plan.get("parks", []):
        px, py = park.get("cx", 0.0), park.get("cy", 0.0)
        pw, ph = park.get("w", 40.0), park.get("h", 40.0)
        for _ in range(int(110 * density)):
            put(R.choice(["grass_tuft", "grass_tuft_2", "grass_bermuda",
                          "fern", "bush", "weed_dandelion"]),
                px + R.uniform(-pw * 0.46, pw * 0.46),
                py + R.uniform(-ph * 0.46, ph * 0.46),
                scale=R.uniform(0.8, 1.6))
        for _ in range(int(7 * density)):
            put(R.choice(["boulder", "dead_trunk", "potted_plant"]),
                px + R.uniform(-pw * 0.4, pw * 0.4),
                py + R.uniform(-ph * 0.4, ph * 0.4))

    # --- weeds in road cracks and at the kerb line -----------------------
    for _ in range(int(70 * density)):
        put(R.choice(["weed_dandelion", "weed_nettle", "grass_bermuda"]),
            R.uniform(-half, half), R.uniform(-half, half),
            scale=R.uniform(0.5, 1.0))

    # --- roof units -------------------------------------------------------
    roofs = [o for o in bpy.data.objects if o.name.startswith("RoofDeck")]
    for ob in roofs:
        if R.random() > 0.35:
            continue
        put("aircon", ob.location.x + R.uniform(-2.5, 2.5),
            ob.location.y + R.uniform(-2.5, 2.5),
            z=ob.location.z + 0.35, jitter=False)

    print("  scanned models: {} instances from {} sources".format(
        n, len([v for v in _LOADED.values() if v])))
    return n


if __name__ == "__main__":
    C.bootstrap(banner="M17 SCANNED MODELS")
    C.build_all_materials()
    build()
    C.report()
