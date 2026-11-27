# =============================================================================
#  BAKE THE ASSET LIBRARY
#  blender -b -P tools/build_library.py -- [--only k1,k2] [--tag tree] [--force]
#
#  Reads the raw Poly Haven scans in assets/raw/, decimates each to its
#  triangle budget, normalises it to a real-world height, drops it to sit on
#  z=0, and writes a compact assets/lib/<key>.glb.
#
#  Raw scans total gigabytes and are gitignored; the baked library is a few
#  megabytes and is committed, so a fresh clone gets the whole set instantly.
# =============================================================================
import glob
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from catalog import MODELS, by_tag

RAW_DIR = os.path.join(HERE, "assets", "raw")
LIB_DIR = os.path.join(HERE, "assets", "lib")

# Baked textures are embedded in the .glb and the whole library is committed,
# so they are downscaled. 512 px is plenty for props seen from street distance
# and keeps the library in the tens of megabytes rather than hundreds.
TEX_MAX = 512


def argv():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def wipe():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bake(key, spec, force=False):
    out = os.path.join(LIB_DIR, key + ".glb")
    if os.path.exists(out) and not force:
        return None

    folder = os.path.join(RAW_DIR, key)
    hits = sorted(glob.glob(os.path.join(folder, "*.gltf")) +
                  glob.glob(os.path.join(folder, "*.glb")))
    if not hits:
        return ("missing", 0, 0)

    wipe()
    try:
        bpy.ops.import_scene.gltf(filepath=hits[0])
    except Exception as exc:
        print("  !! {:18s} import: {}".format(key, exc), flush=True)
        return ("import failed", 0, 0)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        return ("no mesh", 0, 0)

    # join everything into one object
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        try:
            bpy.ops.object.join()
        except Exception:
            pass
    ob = bpy.context.view_layer.objects.active
    before = tri_count(ob)

    # decimate to budget
    budget = spec["tris"]
    if before > budget * 1.2:
        mod = ob.modifiers.new("decimate", "DECIMATE")
        mod.ratio = max(0.004, float(budget) / float(before))
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as exc:
            print("  !! {:18s} decimate: {}".format(key, exc), flush=True)
    after = tri_count(ob)

    # normalise height, centre on XY, sit on the ground
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    dims = ob.dimensions
    if dims.z > 1e-6:
        s = spec["height"] / dims.z
        ob.scale = (s, s, s)
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bb = [ob.matrix_world @ v.co for v in ob.data.vertices]
    if bb:
        min_z = min(v.z for v in bb)
        cx = sum(v.x for v in bb) / len(bb)
        cy = sum(v.y for v in bb) / len(bb)
        ob.location = (ob.location.x - cx, ob.location.y - cy, ob.location.z - min_z)
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    # downscale embedded textures before export
    for img in bpy.data.images:
        try:
            if img.size[0] > TEX_MAX or img.size[1] > TEX_MAX:
                w, h = img.size
                scale = TEX_MAX / float(max(w, h))
                img.scale(max(1, int(w * scale)), max(1, int(h * scale)))
        except Exception:
            pass

    ob.name = key
    os.makedirs(LIB_DIR, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=out, export_format="GLB", use_selection=True,
        export_apply=True, export_cameras=False, export_lights=False,
        export_yup=True, export_image_format="JPEG")
    size = os.path.getsize(out) / 1e6
    return ("ok", before, after, size)


def main():
    args = argv()
    only, tag, force = [], "", False
    i = 0
    while i < len(args):
        if args[i] == "--only" and i + 1 < len(args):
            only = [s.strip() for s in args[i + 1].split(",") if s.strip()]; i += 2
        elif args[i] == "--tag" and i + 1 < len(args):
            tag = args[i + 1]; i += 2
        elif args[i] == "--force":
            force = True; i += 1
        else:
            i += 1

    keys = by_tag(tag) if tag else list(MODELS)
    if only:
        keys = [k for k in keys if k in only]

    os.makedirs(LIB_DIR, exist_ok=True)
    print("baking {} assets -> {}".format(len(keys), LIB_DIR), flush=True)
    t0 = time.time()
    done = skipped = failed = 0
    total_mb = 0.0
    for key in keys:
        res = bake(key, MODELS[key], force=force)
        if res is None:
            skipped += 1
            continue
        if res[0] != "ok":
            print("  -- {:18s} {}".format(key, res[0]), flush=True)
            failed += 1
            continue
        _, before, after, size = res
        total_mb += size
        done += 1
        print("  {:18s} {:>9,} -> {:>7,} tris   {:.2f} MB".format(
            key, before, after, size), flush=True)
    print("baked {}  skipped {}  failed {}  total {:.1f} MB  in {:.0f}s".format(
        done, skipped, failed, total_mb, time.time() - t0), flush=True)


main()
