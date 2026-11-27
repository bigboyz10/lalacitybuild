# =============================================================================
#  CITY BUILD  --  LA STYLE
#  The things that make a city read as Los Angeles rather than anywhere else:
#
#    * palms      Mexican fan palms (Washingtonia) with the dead-frond skirt, and
#                 fat Canary Island date palms. Grown procedurally, instanced.
#    * backdrop   San Gabriel-style mountain wall to the north, low foothills
#                 elsewhere, and a dusty apron so the horizon is never void.
#    * strip mall one-storey shop row with a pole sign and a striped surface
#                 parking lot out front, palms along the kerb.
#
#  standalone:  blender -b -P la_style.py -- --quality preview
# =============================================================================
import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, U, rng, plan_city, add_box
from buildings_core import BASE_Z, emit_building

GOLDEN = math.radians(137.5)


# -----------------------------------------------------------------------------
# small mesh helpers
# -----------------------------------------------------------------------------
def _finish(name, bm, mat, col, smooth=False, hide=False):
    if len(bm.faces) == 0:
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    C.link_object(ob, col)
    ob.data.materials.append(C.M(mat))
    if hide:
        ob.hide_render = True
        ob.hide_viewport = True
    return ob


# -----------------------------------------------------------------------------
# palms
# -----------------------------------------------------------------------------
def _trunk(R, height, r_base, r_top, lean, sides=9):
    """Tapered trunk with a root flare and faint leaf-scar banding."""
    bm = bmesh.new()
    n = max(10, int(height / 0.55))
    ang = R.uniform(0, math.tau)
    lx, ly = math.cos(ang) * lean, math.sin(ang) * lean
    rings = []
    for i in range(n + 1):
        t = i / n
        r = r_top + (r_base - r_top) * (1.0 - t) ** 0.85
        if t < 0.05:
            r *= 1.0 + (0.05 - t) * 7.0          # root flare
        r *= 1.025 if i % 2 else 0.99            # leaf-scar rings
        off = t * t
        cx, cy = lx * off, ly * off
        ring = []
        for k in range(sides):
            a = k / sides * math.tau
            ring.append(bm.verts.new((cx + math.cos(a) * r,
                                      cy + math.sin(a) * r, height * t)))
        rings.append(ring)
    for i in range(n):
        a, b = rings[i], rings[i + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((a[k], a[k2], b[k2], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return bm, Vector((lx, ly, height))


def _fan_frond(bm, o, az, el0, plen, brad, droop, nleaf=11, spread=2.3, wleaf=0.15):
    """One Washingtonia frond: arched petiole then a fan of spiky leaflets."""
    ca, sa = math.cos(az), math.sin(az)
    side = Vector((-sa, ca, 0.0))
    steps = 5
    el = el0
    p = Vector(o)
    pts = [p.copy()]
    for _ in range(steps):
        el -= droop * 0.20
        step = plen / steps
        p = p + Vector((ca * math.cos(el) * step, sa * math.cos(el) * step,
                        math.sin(el) * step))
        pts.append(p.copy())
    w = 0.04
    left = [bm.verts.new(q - side * w) for q in pts]
    right = [bm.verts.new(q + side * w) for q in pts]
    for i in range(steps):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
    tip = pts[-1]
    end = (pts[-1] - pts[-2]).normalized()
    for j in range(nleaf):
        u = (j / (nleaf - 1) - 0.5) * spread
        d = end * math.cos(u) + side * math.sin(u)
        d.z -= 0.22 * abs(math.sin(u)) + 0.10 * droop
        d.normalize()
        L = brad * (1.0 - 0.16 * abs(u))
        mid = tip + d * (L * 0.5) + Vector((0, 0, -0.10 * droop))
        far = tip + d * L + Vector((0, 0, -0.34 * droop - 0.10))
        n_ = d.cross(Vector((0, 0, 1)))
        if n_.length < 1e-4:
            n_ = side.copy()
        n_.normalize()
        v = [bm.verts.new(tip + n_ * 0.02), bm.verts.new(mid + n_ * wleaf),
             bm.verts.new(far), bm.verts.new(mid - n_ * wleaf),
             bm.verts.new(tip - n_ * 0.02)]
        bm.faces.new(v)


def _feather_frond(bm, o, az, el0, length, width, droop):
    """Canary-palm frond: a long arching feather, tapered at both ends."""
    ca, sa = math.cos(az), math.sin(az)
    side = Vector((-sa, ca, 0.0))
    steps = 7
    el = el0
    p = Vector(o)
    pts = [p.copy()]
    for _ in range(steps):
        el -= droop * 0.30
        step = length / steps
        p = p + Vector((ca * math.cos(el) * step, sa * math.cos(el) * step,
                        math.sin(el) * step))
        pts.append(p.copy())
    left, right = [], []
    for i, q in enumerate(pts):
        s = i / steps
        wd = width * math.sin(math.pi * min(1.0, 0.12 + 0.88 * s)) * 0.5
        fold = 0.18 * wd                         # V-fold so it catches light
        left.append(bm.verts.new(q - side * wd - Vector((0, 0, fold))))
        right.append(bm.verts.new(q + side * wd - Vector((0, 0, fold))))
    for i in range(steps):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))


def build_palm(name, kind, R, col):
    """Return the source parts [trunk, live fronds, dead skirt] of one palm."""
    if kind == "washingtonia":
        height = R.uniform(13.0, 21.0)
        trunk_bm, top = _trunk(R, height, R.uniform(0.30, 0.38),
                               R.uniform(0.17, 0.22), R.uniform(0.2, 1.4))
        crown = bmesh.new()
        dead = bmesh.new()
        tiers = [(8, 62, 1.15, 0.95, 0.45), (10, 36, 1.65, 1.15, 0.70),
                 (8, 10, 2.05, 1.25, 0.95)]
        az0 = R.uniform(0, math.tau)
        k = 0
        for (count, el_deg, plen, brad, droop) in tiers:
            for _ in range(count):
                az = az0 + k * GOLDEN + R.uniform(-0.15, 0.15)
                _fan_frond(crown, top + Vector((0, 0, R.uniform(-0.1, 0.15))),
                           az, math.radians(el_deg + R.uniform(-7, 7)),
                           plen * R.uniform(0.9, 1.1), brad * R.uniform(0.9, 1.1),
                           droop)
                k += 1
        # the dead-frond skirt that makes a Washingtonia unmistakable
        for i in range(R.randint(16, 22)):
            az = az0 + i * GOLDEN
            z = top.z - R.uniform(0.15, 2.6)
            ox = top.x * (z / height) ** 2
            oy = top.y * (z / height) ** 2
            r = 0.2
            _fan_frond(dead, Vector((ox + math.cos(az) * r, oy + math.sin(az) * r, z)),
                       az, math.radians(R.uniform(-80, -55)), 1.6, 0.95, -0.15,
                       nleaf=9, spread=1.5, wleaf=0.13)
        parts = [(trunk_bm, "palm_bark", True), (crown, "palm_frond", False),
                 (dead, "palm_dead", False)]
    else:                                       # canary island date palm
        height = R.uniform(7.5, 11.0)
        trunk_bm, top = _trunk(R, height, R.uniform(0.62, 0.78),
                               R.uniform(0.50, 0.62), R.uniform(0.0, 0.5), sides=10)
        crown = bmesh.new()
        az0 = R.uniform(0, math.tau)
        for i in range(46):
            tier = i / 46.0
            el = math.radians(78 - 66 * tier + R.uniform(-6, 6))
            _feather_frond(crown, top + Vector((0, 0, 0.1)),
                           az0 + i * GOLDEN, el,
                           R.uniform(3.8, 5.0) * (0.8 + 0.3 * tier),
                           R.uniform(0.9, 1.3), 0.55 + 0.6 * tier)
        parts = [(trunk_bm, "palm_bark", True), (crown, "palm_frond", False)]

    out = []
    for i, (bm, mat, smooth) in enumerate(parts):
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        ob = _finish("{}_{}".format(name, i), bm, mat, col, smooth=smooth, hide=True)
        if ob:
            out.append(ob)
    return out


def _instance(parts, name, col, loc, rot, scale):
    for src in parts:
        ob = bpy.data.objects.new(name + "_" + src.name.split("_")[-1], src.data)
        ob.location = loc
        ob.rotation_euler = (0.0, 0.0, rot)
        ob.scale = (scale, scale, scale)
        C.link_object(ob, col)


def request_palm(x, y):
    """Called by other modules (houses, strip malls) before la_style.build()."""
    lst = C.get_asset("la_extra_palms", None)
    if lst is None:
        lst = []
        C.set_asset("la_extra_palms", lst)
    lst.append((x, y))


def build_palms(R, plan):
    src = C.col("CITY_LA_src")
    col = C.col("CITY_LA")
    washing = [build_palm("Palm_W{}".format(i), "washingtonia", R, src) for i in range(5)]
    canary = [build_palm("Palm_C{}".format(i), "canary", R, src) for i in range(2)]
    half = plan["half"]
    density = CONFIG.get("density", 0.85)
    n = 0

    def put(x, y, kind=None):
        nonlocal n
        if abs(x) > half or abs(y) > half:
            return
        kind = kind or ("w" if R.random() < 0.75 else "c")
        parts = R.choice(washing if kind == "w" else canary)
        if not parts:
            return
        _instance(parts, "Palm_{:04d}".format(n), col,
                  (x + R.gauss(0, 0.10), y + R.gauss(0, 0.10), BASE_Z),
                  R.uniform(0, math.tau), R.uniform(0.85, 1.20))
        n += 1

    # 1. palm-lined boulevards: take the street-tree slots trees.py handed over
    pits = C.get_asset("tree_pits", [])
    sw = U["sidewalk"]
    if pits:
        for (x, y) in pits:
            if C.la_palm_slot(x, y) and R.random() < 0.95 * density:
                put(x, y, "w" if R.random() < 0.85 else "c")
    else:
        spacing = 11.0
        for blk in plan["blocks"]:
            cx, cy, bw, bh = blk["cx"], blk["cy"], blk["w"], blk["h"]
            for (along, cross, horiz) in ((bw, bh, True), (bh, bw, False)):
                count = max(0, int(along / spacing))
                for i in range(count):
                    t = (i + 0.5) / max(1, count) - 0.5
                    for sgn in (-1, 1):
                        if horiz:
                            x, y = cx + along * t, cy + sgn * (cross * 0.5 + sw * 0.42)
                        else:
                            y, x = cy + along * t, cx + sgn * (cross * 0.5 + sw * 0.42)
                        if C.la_palm_slot(x, y) and R.random() < 0.8 * density:
                            put(x, y, "w")

    # 2. palms other modules asked for (front yards, parking lots)
    for (x, y) in C.get_asset("la_extra_palms", []) or []:
        put(x, y)

    # 3. parks: a grove of canary palms plus scattered fan palms
    for park in plan.get("parks", []):
        for _ in range(int(9 * density)):
            put(R.uniform(park["x0"] + 4, park["x1"] - 4),
                R.uniform(park["y0"] + 4, park["y1"] - 4),
                "c" if R.random() < 0.4 else "w")
    print("  palms: {} instances from {} grown variants".format(
        n, len(washing) + len(canary)))
    return n


# -----------------------------------------------------------------------------
# backdrop: mountains + apron
# -----------------------------------------------------------------------------
def build_backdrop(R, plan):
    col = C.col("CITY_LA")
    half = plan["half"]
    r_in = half * 2.2 + 500.0
    depth = 2400.0
    n_theta, n_r = 180, 8
    ph = [R.uniform(0, math.tau) for _ in range(8)]

    def ridge(th):
        # +Y is north: the big San Gabriel wall; low foothills east/west;
        # nothing to the south (ocean side)
        north = max(0.0, math.sin(th)) ** 1.3
        n1 = (math.sin(th * 3 + ph[0]) + 0.6 * math.sin(th * 7 + ph[1]) +
              0.35 * math.sin(th * 13 + ph[2]) + 0.2 * math.sin(th * 29 + ph[3]))
        n1 = 0.5 + 0.5 * n1 / 2.15
        sides = (abs(math.cos(th)) ** 1.5) * (0.5 + 0.5 * math.sin(th * 5 + ph[4]))
        h = 820.0 * north * (0.45 + 0.55 * n1) + 170.0 * sides * (0.4 + 0.6 * n1)
        return max(0.0, h)

    bm = bmesh.new()
    rings = []
    for j in range(n_r + 1):
        u = j / n_r
        r = r_in + u * depth
        prof = math.sin(min(1.0, u / 0.55) * math.pi * 0.5) if u < 0.55 else \
            max(0.0, 1.0 - (u - 0.55) * 0.9)
        ring = []
        for i in range(n_theta):
            th = i / n_theta * math.tau
            h = ridge(th) * prof
            h += 28.0 * prof * math.sin(th * 41 + u * 8.0 + ph[5]) * \
                math.sin(th * 17 + ph[6])
            ring.append(bm.verts.new((r * math.cos(th), r * math.sin(th),
                                      BASE_Z - 0.6 + max(0.0, h))))
        rings.append(ring)
    for j in range(n_r):
        a, b = rings[j], rings[j + 1]
        for i in range(n_theta):
            i2 = (i + 1) % n_theta
            bm.faces.new((a[i], a[i2], b[i2], b[i]))
    _finish("LA_Mountains", bm, "la_mountain", col, smooth=True)

    # dusty apron so the horizon is ground, not void
    bm2 = bmesh.new()
    bmesh.ops.create_circle(bm2, cap_ends=True, radius=r_in + depth + 600.0,
                            segments=72)
    for v in bm2.verts:
        v.co.z = BASE_Z - 0.62
    _finish("LA_Apron", bm2, "la_ground", col)
    print("  backdrop: mountain ring r={:.0f}-{:.0f} m".format(r_in, r_in + depth))


# -----------------------------------------------------------------------------
# strip mall
# -----------------------------------------------------------------------------
def strip_mall(name, rect, R, collection, detail):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    depth = max(9.0, min(h * 0.42, 15.0))
    bld = (x0, y1 - depth, x1, y1)
    res = emit_building(name, bld, 5.6, "strip_mall", collection, R,
                        detail=detail, ground_floor=True)

    # surface lot in front (south): asphalt, stall stripes, kerb planter strip
    ya, yb = y0 + 0.5, y1 - depth - 0.4
    lot_d = yb - ya
    cx = (x0 + x1) * 0.5
    if lot_d > 6.0:
        add_box(name + "_Lot", (w - 0.6, lot_d, 0.06), loc=(cx, (ya + yb) * 0.5, BASE_Z + 0.03),
                mat="asphalt", collection=collection)
        bm = bmesh.new()
        stall_w, stall_d = 2.7, 5.4
        rows = [yb - stall_d]
        if lot_d >= stall_d * 2 + 6.2:
            rows.append(ya)
        for ry in rows:
            x = x0 + 0.5
            while x <= x1 - 0.5:
                v = [bm.verts.new((x - 0.05, ry, BASE_Z + 0.07)),
                     bm.verts.new((x + 0.05, ry, BASE_Z + 0.07)),
                     bm.verts.new((x + 0.05, ry + stall_d, BASE_Z + 0.07)),
                     bm.verts.new((x - 0.05, ry + stall_d, BASE_Z + 0.07))]
                bm.faces.new(v)
                x += stall_w
        _finish(name + "_Stalls", bm, "paint_white", collection)
    # pole sign
    px = x0 + w * R.choice([0.12, 0.88])
    py = y0 + 1.2
    add_box(name + "_SignPole", (0.45, 0.45, 8.5), loc=(px, py, BASE_Z + 4.25),
            mat="metal_dark", collection=collection)
    add_box(name + "_SignBox", (3.4, 0.45, 2.6), loc=(px, py, BASE_Z + 8.6),
            mat=R.choice(["paint_red", "paint_yellow", "paint_green", "paint_white"]),
            collection=collection)
    # palms along the kerb edge of the lot
    for k in range(R.randint(1, 3)):
        request_palm(x0 + (k + 0.5) * w / 3.0 + R.uniform(-2, 2), y0 + 0.9)
    return res


# -----------------------------------------------------------------------------
def build():
    if not C.is_la():
        return 0
    R = rng("la_style")
    plan = plan_city()
    build_backdrop(R, plan)
    return build_palms(R, plan)


if __name__ == "__main__":
    C.bootstrap(banner="LA STYLE")
    C.build_all_materials()
    build()
    C.report()
