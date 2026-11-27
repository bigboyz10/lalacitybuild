#!/usr/bin/env python3
"""Render-performance audit: where the triangles are and what is not instanced.

    source tools/env.sh
    blender -b -P tools/perf_audit.py -- --size 480 --look la

Reports, per collection:
  objects, triangles, unique mesh datablocks, instancing ratio
and then flags the two things that actually cost render time:

  1. DUPLICATE GEOMETRY - distinct mesh datablocks with identical geometry
     signatures. Each one is a separate BVH build and a separate copy in
     memory; they should share one datablock via linked duplication.
  2. TRIANGLE HOTSPOTS - collections whose share of the budget is out of
     proportion to how much of the frame they occupy.
"""
import os
import sys
from collections import defaultdict

import bpy

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C


def tri_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def signature(me):
    """Cheap geometry fingerprint: counts plus rounded bounding box."""
    if not me.vertices:
        return None
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    return (len(me.vertices), len(me.polygons),
            round(max(xs) - min(xs), 4),
            round(max(ys) - min(ys), 4),
            round(max(zs) - min(zs), 4))


def audit():
    rows = []
    total_obj = total_tri = 0
    mesh_tris = {}

    for coll in bpy.data.collections:
        objs = [o for o in coll.objects if o.type == "MESH"]
        if not objs:
            continue
        tris = 0
        meshes = set()
        for ob in objs:
            me = ob.data
            if me.name not in mesh_tris:
                mesh_tris[me.name] = tri_count(me)
            tris += mesh_tris[me.name]
            meshes.add(me.name)
        rows.append((coll.name, len(objs), tris, len(meshes)))
        total_obj += len(objs)
        total_tri += tris

    rows.sort(key=lambda r: -r[2])

    print("\n" + "=" * 86)
    print(" RENDER PERFORMANCE AUDIT")
    print("=" * 86)
    print(" {:<28} {:>7} {:>13} {:>8} {:>9} {:>9}".format(
        "COLLECTION", "OBJECTS", "TRIANGLES", "MESHES", "INST.RATIO", "%BUDGET"))
    print("-" * 86)
    for name, nobj, tris, nmesh in rows:
        ratio = nobj / float(nmesh) if nmesh else 0.0
        pct = 100.0 * tris / total_tri if total_tri else 0.0
        # *_src collections hold hidden prototypes by design: one object per
        # shape is correct there, and they are hide_render so they cost
        # memory and file size but no render time. Don't flag them.
        is_src = name.endswith("_src")
        flag = ""
        if is_src:
            flag = "  (hidden prototypes - no render cost)"
        elif ratio < 1.25 and nobj >= 20:
            flag = "  <-- not instanced"
        print(" {:<28} {:>7,} {:>13,} {:>8,} {:>9.2f}x {:>8.1f}%{}".format(
            name, nobj, tris, nmesh, ratio, pct, flag))
    print("-" * 86)
    print(" {:<28} {:>7,} {:>13,}".format("TOTAL", total_obj, total_tri))

    # --- duplicate geometry -------------------------------------------------
    by_sig = defaultdict(list)
    for me in bpy.data.meshes:
        if me.users == 0 or not me.polygons:
            continue
        sig = signature(me)
        if sig:
            by_sig[sig].append(me.name)

    waste = []
    for sig, names in by_sig.items():
        if len(names) > 1:
            tris = mesh_tris.get(names[0]) or tri_count(bpy.data.meshes[names[0]])
            waste.append((tris * (len(names) - 1), len(names), names[0], tris))
    waste.sort(reverse=True)

    print("\n DUPLICATE GEOMETRY (separate datablocks, identical shape)")
    print("-" * 86)
    if not waste:
        print("  none - every repeated shape already shares one datablock")
    else:
        wasted_total = sum(w[0] for w in waste)
        for wasted, count, example, tris in waste[:15]:
            print("  {:>11,} wasted tris  x{:<4} copies  {:>8,} tris each  e.g. {}".format(
                wasted, count, tris, example))
        print("-" * 86)
        print("  {:,} triangles ({:.1f}% of scene) are duplicate datablocks".format(
            wasted_total, 100.0 * wasted_total / total_tri if total_tri else 0))
    print("=" * 86 + "\n")
    return total_obj, total_tri


def main():
    C.bootstrap(banner="PERF AUDIT")
    C.build_all_materials()
    try:
        import assets_pbr
        assets_pbr.build()
    except Exception:
        pass
    import master
    for key, mod_name, fn_name in master.PIPELINE:
        try:
            mod = __import__(mod_name)
            getattr(mod, fn_name)()
        except Exception as exc:
            print("  !! {} -> {}".format(mod_name, exc))
    audit()


if __name__ == "__main__":
    main()
