# =============================================================================
#  CITY BUILD  --  M2 : ROAD NETWORK
#  standalone:  blender -b -P roads.py -- --quality preview
#
#  Builds every carriageway from the masterplan: surfaces, lane paint,
#  crosswalks, stop bars, turn arrows, patches, cracks, potholes, gutters,
#  drains, manholes, speed tables.
# =============================================================================
import bpy
import bmesh
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, plan_city, rng, add_box, add_plane, add_cylinder

Z_SURFACE = 0.020
Z_WEAR = 0.0208
Z_PATCH = 0.0215
Z_PAINT = 0.030
Z_POTHOLE = 0.024
Z_MANHOLE = 0.028
Z_DRAIN = 0.026


# -----------------------------------------------------------------------------
# low level mesh helpers
# -----------------------------------------------------------------------------
def _add_box_bm(bm, cx, cy, cz, sx, sy, sz, rot=0.0):
    ca, sa = math.cos(rot), math.sin(rot)
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    bot = []
    top = []
    for (px, py) in corners:
        wx = cx + px * ca - py * sa
        wy = cy + px * sa + py * ca
        bot.append(bm.verts.new((wx, wy, cz - hz)))
        top.append(bm.verts.new((wx, wy, cz + hz)))
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((bot[i], bot[j], top[j], top[i]))


def _mesh_from_bm(name, bm, mat, collection, smooth=False):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    C.link_object(obj, collection)
    if mat:
        obj.data.materials.append(C.M(mat))
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    return obj


def _paint_object(name, prims, z, mat, collection):
    """prims: list of ('q', cx, cy, sx, sy, rot) or ('t', cx, cy, size, rot)."""
    bm = bmesh.new()
    for prim in prims:
        if prim[0] == "q":
            _, cx, cy, sx, sy, rot = prim
            ca, sa = math.cos(rot), math.sin(rot)
            hx, hy = sx * 0.5, sy * 0.5
            pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
            vs = [bm.verts.new((cx + px * ca - py * sa,
                                cy + px * sa + py * ca, z)) for (px, py) in pts]
            bm.faces.new(vs)
        else:
            _, cx, cy, size, rot = prim
            ca, sa = math.cos(rot), math.sin(rot)
            pts = [(0.0, size * 0.62), (-size * 0.55, -size * 0.45),
                   (size * 0.55, -size * 0.45)]
            vs = [bm.verts.new((cx + px * ca - py * sa,
                                cy + px * sa + py * ca, z)) for (px, py) in pts]
            bm.faces.new(vs)
    if len(bm.faces) == 0:
        bm.free()
        return None
    return _mesh_from_bm(name, bm, mat, collection)


# -----------------------------------------------------------------------------
# segment solver
# -----------------------------------------------------------------------------
def _segments(plan):
    half = plan["half"]
    ew_edges = sorted((r["c"] - r["w"] * 0.5, r["c"] + r["w"] * 0.5)
                      for r in plan["roads_y"])
    ns_edges = sorted((r["c"] - r["w"] * 0.5, r["c"] + r["w"] * 0.5)
                      for r in plan["roads_x"])
    segs = []
    for r in plan["roads_x"]:
        a = -half
        for (lo, hi) in ew_edges:
            if lo > a + 0.6:
                segs.append({"axis": "ns", "c": r["c"], "w": r["w"],
                             "a": a, "b": lo, "kind": r["kind"]})
            a = max(a, hi)
        if a < half - 0.6:
            segs.append({"axis": "ns", "c": r["c"], "w": r["w"],
                         "a": a, "b": half, "kind": r["kind"]})
    for r in plan["roads_y"]:
        a = -half
        for (lo, hi) in ns_edges:
            if lo > a + 0.6:
                segs.append({"axis": "ew", "c": r["c"], "w": r["w"],
                             "a": a, "b": lo, "kind": r["kind"]})
            a = max(a, hi)
        if a < half - 0.6:
            segs.append({"axis": "ew", "c": r["c"], "w": r["w"],
                         "a": a, "b": half, "kind": r["kind"]})
    return segs


def _seg_len(s):
    return s["b"] - s["a"]


def _seg_mid(s):
    return (s["a"] + s["b"]) * 0.5


# -----------------------------------------------------------------------------
# surfaces
# -----------------------------------------------------------------------------
def build_surfaces(segs, collection):
    R = rng("roads_surface")
    buckets = {}
    for s in segs:
        L = _seg_len(s)
        if L < 1.0:
            continue
        roll = R.random()
        if s["kind"] == "arterial":
            mat = "asphalt_wet" if roll < 0.10 else "asphalt"
        elif roll < 0.16:
            mat = "asphalt_patch"
        else:
            mat = "asphalt"
        buckets.setdefault(mat, []).append(s)

    objs = []
    for mat, group in buckets.items():
        bm = bmesh.new()
        for s in group:
            L = _seg_len(s)
            mid = _seg_mid(s)
            if s["axis"] == "ns":
                _add_box_bm(bm, s["c"], mid, Z_SURFACE - 0.05, s["w"], L, 0.10)
            else:
                _add_box_bm(bm, mid, s["c"], Z_SURFACE - 0.05, L, s["w"], 0.10)
        objs.append(_mesh_from_bm("Road_Surface_" + mat, bm, mat, collection))

    # intersections
    bm = bmesh.new()
    for it in plan_intersections:
        _add_box_bm(bm, it["x"], it["y"], Z_SURFACE - 0.05,
                    it["w"], it["h"], 0.10)
    if len(bm.faces):
        objs.append(_mesh_from_bm("Road_Intersections", bm, "asphalt", collection))
    return objs


# -----------------------------------------------------------------------------
# paint
# -----------------------------------------------------------------------------
def build_markings(segs, collection):
    R = rng("roads_paint")
    white = []
    yellow = []

    for s in segs:
        L = _seg_len(s)
        if L < 2.0:
            continue
        mid = _seg_mid(s)
        w = s["w"]
        lanes = max(2, int(round(w / 3.0)))

        if s["axis"] == "ns":
            # double yellow centre
            for off in (-0.16, 0.16):
                yellow.append(("q", s["c"] + off, mid, 0.12, L - 0.6, 0.0))
            # lane dashes
            if lanes >= 4:
                for k in range(1, lanes // 2):
                    for sgn in (-1, 1):
                        x = s["c"] + sgn * (3.0 * k)
                        y = s["a"] + 3.0
                        while y < s["b"] - 3.0:
                            white.append(("q", x, y, 0.12, 3.0, 0.0))
                            y += 9.0
            # edge lines
            for sgn in (-1, 1):
                white.append(("q", s["c"] + sgn * (w * 0.5 - 0.35), mid,
                              0.15, L - 0.4, 0.0))
        else:
            for off in (-0.16, 0.16):
                yellow.append(("q", mid, s["c"] + off, L - 0.6, 0.12, 0.0))
            if lanes >= 4:
                for k in range(1, lanes // 2):
                    for sgn in (-1, 1):
                        y = s["c"] + sgn * (3.0 * k)
                        x = s["a"] + 3.0
                        while x < s["b"] - 3.0:
                            white.append(("q", x, y, 3.0, 0.12, 0.0))
                            x += 9.0
            for sgn in (-1, 1):
                white.append(("q", mid, s["c"] + sgn * (w * 0.5 - 0.35),
                              L - 0.4, 0.15, 0.0))

    _paint_object("Road_Paint_White", white, Z_PAINT, "paint_white", collection)
    _paint_object("Road_Paint_Yellow", yellow, Z_PAINT, "paint_yellow", collection)


def build_crosswalks(collection):
    white = []
    for it in plan_intersections:
        cx, cy = it["x"], it["y"]
        wns, wew = it["w"], it["h"]
        depth = 2.6
        # north + south crossings (over the N-S street)
        for sgn in (-1, 1):
            yc = cy + sgn * (wew * 0.5 + 2.2)
            x = cx - wns * 0.5 + 0.45
            while x < cx + wns * 0.5 - 0.45:
                white.append(("q", x, yc, 0.55, depth, 0.0))
                x += 1.15
        # east + west crossings (over the E-W street)
        for sgn in (-1, 1):
            xc = cx + sgn * (wns * 0.5 + 2.2)
            y = cy - wew * 0.5 + 0.45
            while y < cy + wew * 0.5 - 0.45:
                white.append(("q", xc, y, depth, 0.55, 0.0))
                y += 1.15

    # stop bars on the four approaches
    for it in plan_intersections:
        cx, cy = it["x"], it["y"]
        wns, wew = it["w"], it["h"]
        white.append(("q", cx + wns * 0.25, cy + wew * 0.5 + 3.9,
                      wns * 0.5 - 0.5, 0.45, 0.0))
        white.append(("q", cx - wns * 0.25, cy - wew * 0.5 - 3.9,
                      wns * 0.5 - 0.5, 0.45, 0.0))
        white.append(("q", cx + wns * 0.5 + 3.9, cy - wew * 0.25,
                      0.45, wew * 0.5 - 0.5, 0.0))
        white.append(("q", cx - wns * 0.5 - 3.9, cy + wew * 0.25,
                      0.45, wew * 0.5 - 0.5, 0.0))

    _paint_object("Road_Crosswalks", white, Z_PAINT, "paint_white", collection)


def build_arrows(segs, collection):
    R = rng("roads_arrows")
    white = []
    for s in segs:
        if s["kind"] == "residential":
            continue
        if _seg_len(s) < 14.0:
            continue
        lanes = max(2, int(round(s["w"] / 3.0)))
        for k in range(lanes):
            if R.random() > 0.55:
                continue
            if s["axis"] == "ns":
                off = -s["w"] * 0.5 + 1.5 + k * 3.0
                y = s["a"] + 7.0 + R.uniform(0.0, 3.0)
                white.append(("q", s["c"] + off, y, 0.34, 2.0, 0.0))
                white.append(("t", s["c"] + off, y + 1.35, 0.85, 0.0))
            else:
                off = -s["w"] * 0.5 + 1.5 + k * 3.0
                x = s["a"] + 7.0 + R.uniform(0.0, 3.0)
                white.append(("q", x, s["c"] + off, 2.0, 0.34, 0.0))
                white.append(("t", x + 1.35, s["c"] + off, 0.85, math.pi * 0.5))
    _paint_object("Road_Arrows", white, Z_PAINT, "paint_white", collection)


# -----------------------------------------------------------------------------
# wear, patches, cracks, potholes
# -----------------------------------------------------------------------------
def build_wear(segs, collection):
    if CONFIG["quality"] == "preview":
        return
    R = rng("roads_wear")
    prims = []
    for s in segs:
        if s["kind"] == "residential":
            continue
        L = _seg_len(s)
        if L < 8.0:
            continue
        mid = _seg_mid(s)
        lanes = max(2, int(round(s["w"] / 3.0)))
        for k in range(lanes):
            for sgn in (-1, 1):
                off = -s["w"] * 0.5 + 1.5 + k * 3.0 + sgn * 0.85
                if s["axis"] == "ns":
                    prims.append(("q", s["c"] + off, mid, 0.55, L - 1.0, 0.0))
                else:
                    prims.append(("q", mid, s["c"] + off, L - 1.0, 0.55, 0.0))
    _paint_object("Road_WheelWear", prims, Z_WEAR, "asphalt_wet", collection)


def build_patches(segs, collection):
    R = rng("roads_patches")
    prims = []
    for s in segs:
        L = _seg_len(s)
        n = int(L / 26.0) + (1 if R.random() < 0.4 else 0)
        for i in range(n):
            t = R.uniform(0.1, 0.9)
            along = s["a"] + L * t
            across = s["c"] + R.uniform(-s["w"] * 0.36, s["w"] * 0.36)
            sx = R.uniform(1.6, 4.5)
            sy = R.uniform(1.2, 3.2)
            rot = R.uniform(-0.25, 0.25)
            if s["axis"] == "ns":
                prims.append(("q", across, along, sx, sy, rot))
            else:
                prims.append(("q", along, across, sy, sx, rot))
    _paint_object("Road_Patches", prims, Z_PATCH, "asphalt_patch", collection)


def build_cracks(segs, collection):
    R = rng("roads_cracks")
    bm = bmesh.new()
    for s in segs:
        L = _seg_len(s)
        n = int(L / 18.0)
        for i in range(n):
            along = s["a"] + R.uniform(2.0, max(2.1, L - 2.0))
            across = s["c"] + R.uniform(-s["w"] * 0.42, s["w"] * 0.42)
            pts = []
            seg_n = R.randint(3, 6)
            step = R.uniform(0.5, 1.4)
            cx, cy = along, across
            ang = R.uniform(0, math.tau)
            for k in range(seg_n):
                if s["axis"] == "ns":
                    pts.append((across + (cx - along), along + (cy - across)))
                else:
                    pts.append((along + (cx - along), across + (cy - across)))
                ang += R.uniform(-0.9, 0.9)
                cx += math.cos(ang) * step
                cy += math.sin(ang) * step
            width = R.uniform(0.03, 0.09)
            rows = []
            for k, (px, py) in enumerate(pts):
                if k == 0:
                    dx, dy = pts[1][0] - px, pts[1][1] - py
                elif k == len(pts) - 1:
                    dx, dy = px - pts[k - 1][0], py - pts[k - 1][1]
                else:
                    dx = pts[k + 1][0] - pts[k - 1][0]
                    dy = pts[k + 1][1] - pts[k - 1][1]
                ln = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / ln * width * 0.5, dx / ln * width * 0.5
                rows.append((bm.verts.new((px + nx, py + ny, Z_PATCH + 0.001)),
                             bm.verts.new((px - nx, py - ny, Z_PATCH + 0.001))))
            for k in range(len(rows) - 1):
                try:
                    bm.faces.new((rows[k][0], rows[k][1],
                                  rows[k + 1][1], rows[k + 1][0]))
                except ValueError:
                    pass
    if len(bm.faces):
        _mesh_from_bm("Road_Cracks", bm, "asphalt_patch", collection)


def build_potholes(segs, collection):
    R = rng("roads_potholes")
    count = 0
    for s in segs:
        L = _seg_len(s)
        n = int(L / 40.0) + (1 if R.random() < 0.25 else 0)
        for i in range(n):
            along = s["a"] + R.uniform(3.0, max(3.1, L - 3.0))
            across = s["c"] + R.uniform(-s["w"] * 0.38, s["w"] * 0.38)
            r = R.uniform(0.22, 0.62)
            bm = bmesh.new()
            seg = 14
            center = bm.verts.new((0.0, 0.0, 0.0))
            ring = []
            for k in range(seg):
                a = math.tau * k / seg
                rr = r * (0.72 + R.random() * 0.55)
                ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), 0.0)))
            for k in range(seg):
                j = (k + 1) % seg
                bm.faces.new((center, ring[k], ring[j]))
            if s["axis"] == "ns":
                loc = (across, along, Z_POTHOLE)
            else:
                loc = (along, across, Z_POTHOLE)
            obj = _mesh_from_bm("Pothole_{:03d}".format(count), bm,
                                "asphalt_patch", collection)
            obj.location = loc
            count += 1
    return count


# -----------------------------------------------------------------------------
# drainage furniture
# -----------------------------------------------------------------------------
def build_manholes(segs, collection):
    R = rng("roads_manholes")
    count = 0
    for s in segs:
        L = _seg_len(s)
        n = int(L / 55.0) + (1 if R.random() < 0.3 else 0)
        for i in range(n):
            along = s["a"] + R.uniform(4.0, max(4.1, L - 4.0))
            across = s["c"] + R.uniform(-s["w"] * 0.25, s["w"] * 0.25)
            if s["axis"] == "ns":
                loc = (across, along)
            else:
                loc = (along, across)
            add_cylinder("Manhole_{:03d}".format(count), 0.36, 0.05,
                         loc=(loc[0], loc[1], Z_MANHOLE), mat="metal_dark",
                         collection=collection, segments=18)
            add_cylinder("Manhole_Rim_{:03d}".format(count), 0.42, 0.02,
                         loc=(loc[0], loc[1], Z_MANHOLE - 0.02), mat="rust",
                         collection=collection, segments=18)
            count += 1
    return count


def _drain_object(name, cx, cy, rot, collection):
    bm = bmesh.new()
    _add_box_bm(bm, 0.0, 0.0, 0.0, 0.95, 0.55, 0.06, 0.0)
    for i in range(6):
        _add_box_bm(bm, -0.38 + i * 0.152, 0.0, 0.035, 0.07, 0.46, 0.03, 0.0)
    obj = _mesh_from_bm(name, bm, "metal_dark", collection)
    obj.location = (cx, cy, Z_DRAIN)
    obj.rotation_euler = (0.0, 0.0, rot)
    return obj


def build_drains(collection):
    R = rng("roads_drains")
    count = 0
    for it in plan_intersections:
        cx, cy = it["x"], it["y"]
        wns, wew = it["w"], it["h"]
        spots = [
            (cx - wns * 0.5 - 0.55, cy - wew * 0.5 - 0.55, 0.0),
            (cx + wns * 0.5 + 0.55, cy - wew * 0.5 - 0.55, math.pi * 0.5),
            (cx - wns * 0.5 - 0.55, cy + wew * 0.5 + 0.55, math.pi * 0.5),
            (cx + wns * 0.5 + 0.55, cy + wew * 0.5 + 0.55, 0.0),
        ]
        for (sx, sy, rot) in spots:
            if R.random() < 0.15:
                continue
            _drain_object("StormDrain_{:03d}".format(count), sx, sy, rot, collection)
            count += 1
    return count


def build_gutters(segs, collection):
    prims = []
    for s in segs:
        L = _seg_len(s)
        if L < 3.0:
            continue
        mid = _seg_mid(s)
        for sgn in (-1, 1):
            if s["axis"] == "ns":
                prims.append(("q", s["c"] + sgn * (s["w"] * 0.5 - 0.22), mid,
                              0.40, L - 0.5, 0.0))
            else:
                prims.append(("q", mid, s["c"] + sgn * (s["w"] * 0.5 - 0.22),
                              L - 0.5, 0.40, 0.0))
    _paint_object("Road_Gutters", prims, Z_WEAR, "asphalt_wet", collection)


def build_speed_tables(segs, collection):
    R = rng("roads_speed")
    count = 0
    for s in segs:
        if s["kind"] != "residential":
            continue
        L = _seg_len(s)
        if L < 12.0:
            continue
        n = 1 if R.random() < 0.5 else 0
        for i in range(n):
            along = s["a"] + L * R.uniform(0.3, 0.7)
            if s["axis"] == "ns":
                loc = (s["c"], along, Z_SURFACE + 0.05)
                size = (s["w"] - 0.6, 3.6)
            else:
                loc = (along, s["c"], Z_SURFACE + 0.05)
                size = (3.6, s["w"] - 0.6)
            add_box("SpeedTable_{:03d}".format(count), (size[0], size[1], 0.10),
                    loc=loc, mat="asphalt", collection=collection, bevel=0.03)
            count += 1
    return count


# -----------------------------------------------------------------------------
# build
# -----------------------------------------------------------------------------
plan_intersections = []


def build():
    global plan_intersections
    plan = plan_city()
    plan_intersections = plan["intersections"]
    collection = C.col("CITY_Roads")
    segs = _segments(plan)

    build_surfaces(segs, collection)
    build_gutters(segs, collection)
    build_wear(segs, collection)
    build_patches(segs, collection)
    build_cracks(segs, collection)
    build_potholes(segs, collection)
    build_manholes(segs, collection)
    build_drains(collection)
    build_markings(segs, collection)
    build_crosswalks(collection)
    build_arrows(segs, collection)
    build_speed_tables(segs, collection)

    C.set_asset("road_segments", segs)
    print("  road segments: {}  intersections: {}".format(
        len(segs), len(plan_intersections)))
    return plan


if __name__ == "__main__":
    C.bootstrap(banner="M2 ROADS")
    C.build_all_materials()
    build()
    C.report()