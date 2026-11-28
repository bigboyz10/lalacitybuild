# =============================================================================
#  CITY BUILD  --  M1 : TERRAIN, MASTERPLAN GROUND, WATERFRONT, ELEVATED ROAD
#  standalone:  blender -b -P terrain.py -- --quality preview
# =============================================================================
import bpy
import bmesh
import math
from mathutils import Matrix, Euler, Vector
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, plan_city, add_box, add_plane, add_grid_surface, add_cylinder, add_rock, rng, fbm


MARGIN = 170.0


# -----------------------------------------------------------------------------
# Terrain height field. Flat and true inside the built area, rolling outside,
# dropping into the river on the south side.
# -----------------------------------------------------------------------------
def ground_z(x, y, half):
    if y < -half:
        t = min(1.0, (-half - y) / 45.0)
        return -2.4 * t * t
    dx = max(0.0, abs(x) - half)
    dy = max(0.0, y - half)
    d = math.hypot(dx, dy)
    if d <= 0.0:
        return 0.0
    t = min(1.0, d / 150.0)
    hills = fbm(x * 0.011, y * 0.011, 4, 7) * 2.2
    ridge = fbm(x * 0.004 + 10.0, y * 0.004, 3, 19) * 9.0
    return (t * t) * (5.0 + ridge) + hills * t


# -----------------------------------------------------------------------------
# Ground shell
# -----------------------------------------------------------------------------
def build_ground(plan, collection):
    half = plan["half"]
    ext = half + MARGIN
    step = 6.0 if CONFIG["quality"] == "preview" else 4.0
    nx = int((2 * ext) / step)
    ny = int((2 * ext) / step)
    obj = add_grid_surface(
        "Terrain_Ground", -ext, ext, -ext, ext, nx, ny,
        lambda x, y: ground_z(x, y, half),
        mat="dirt", collection=collection, smooth=True)
    C.set_asset("ground", obj)
    return obj


def build_block_lots(plan, collection):
    """Flat lot slabs under each block, material chosen by district."""
    R = rng("terrain_lots")
    out = []
    for idx, b in enumerate(plan["blocks"]):
        inset = 0.45
        w = max(1.0, b["w"] - inset * 2)
        h = max(1.0, b["h"] - inset * 2)
        dist = b["district"]
        if dist == "parkland":
            mat = "grass"
        elif dist == "industrial":
            mat = "gravel" if R.random() < 0.6 else "dirt"
        elif dist == "waterfront":
            mat = "concrete_lot"
        else:
            mat = "concrete_lot"
        o = add_plane("Lot_{:03d}_{}".format(idx, dist), (w, h),
                      loc=(b["cx"], b["cy"], 0.006), mat=mat, collection=collection)
        out.append(o)
    return out


# -----------------------------------------------------------------------------
# Waterfront: bulkhead, water, riprap, mooring bollards, embankment kerb
# -----------------------------------------------------------------------------
def build_waterfront(plan, collection):
    half = plan["half"]
    R = rng("terrain_water")
    span = half * 2.0 + 240.0
    wy = -half

    # river surface
    add_plane("Water_River", (span, 260.0),
              loc=(0.0, wy - 130.0, -0.62), mat="water",
              collection=collection, subdiv=24, smooth=True)

    # bulkhead wall (concrete quay)
    add_box("Quay_Bulkhead", (span, 1.30, 2.60),
            loc=(0.0, wy - 0.65, -0.95), mat="concrete",
            collection=collection, bevel=0.03)

    # coping stone on top of the wall
    add_box("Quay_Coping", (span, 1.55, 0.22),
            loc=(0.0, wy - 0.65, 0.40), mat="stone", collection=collection, bevel=0.02)

    # riprap boulders along the water side
    for i in range(70):
        x = R.uniform(-span * 0.5, span * 0.5)
        y = wy - R.uniform(1.8, 7.0)
        z = -0.62 - R.uniform(0.0, 1.4)
        s = R.uniform(0.5, 1.6)
        add_rock("Riprap_{:02d}".format(i), (s * 1.6, s * 1.2, s * 0.8),
                 loc=(x, y, z), rot=(0, 0, R.uniform(0, math.tau)),
                 mat="stone_dark", collection=collection, seed=1000 + i)

    # mooring bollards along the quay
    for i in range(12):
        x = -half + 20.0 + i * (half * 2.0 - 40.0) / 11.0
        add_cylinder("Mooring_Bollard_{:02d}".format(i), 0.22, 0.75,
                     loc=(x, wy - 1.55, 0.52), mat="rust",
                     collection=collection, segments=12)
        add_cylinder("Mooring_Cap_{:02d}".format(i), 0.30, 0.10,
                     loc=(x, wy - 1.55, 0.93), mat="rust",
                     collection=collection, segments=12)

    # ladders down the quay face
    for i in range(4):
        x = -half + 60.0 + i * (half * 2.0 - 120.0) / 3.0
        for r in range(7):
            add_box("Quay_Ladder_{}_{}".format(i, r), (0.06, 0.58, 0.05),
                    loc=(x, wy - 1.35, 0.05 - r * 0.34), mat="metal_dark",
                    collection=collection)
        add_box("Quay_LadderRailL_{}".format(i), (0.05, 0.05, 2.45),
                loc=(x - 0.30, wy - 1.35, -1.05), mat="metal_dark", collection=collection)
        add_box("Quay_LadderRailR_{}".format(i), (0.05, 0.05, 2.45),
                loc=(x + 0.30, wy - 1.35, -1.05), mat="metal_dark", collection=collection)

    # floating pontoon + mooring piles (mid-river)
    add_box("Pontoon", (26.0, 4.0, 0.45), loc=(half * 0.25, wy - 14.0, -0.40),
            mat="wood_pale", collection=collection, bevel=0.02)
    for i in range(4):
        add_cylinder("Pontoon_Pile_{}".format(i), 0.18, 3.2,
                     loc=(half * 0.25 - 12.0 + i * 8.0, wy - 15.9, 0.35),
                     mat="rust", collection=collection, segments=10)

    C.set_asset("water_y", wy)


# -----------------------------------------------------------------------------
# Elevated highway on the north edge  (board task T-007)
#   deck, three families of bents, jittered + finger expansion joints, wheel
#   wear / patches / tar-snake cracks, an off-ramp and an on-ramp on the city
#   side, and overhead sign gantries.  Every random choice comes from
#   rng("highway"), so a given seed always builds the same highway.
# -----------------------------------------------------------------------------
RAMP_W = 6.6          # one lane + shoulders
RAMP_TAPER = 34.0     # length over which a ramp widens out of the deck edge
RAMP_GRADE = 0.06


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _bm_cube(bm, loc, size, rot=(0.0, 0.0, 0.0)):
    m = Matrix.LocRotScale(Vector(loc), Euler(rot, "XYZ"), Vector(size))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def _bm_strip(bm, pts, width, z):
    """Flat ribbon along a 2D polyline, appended to an existing bmesh."""
    rows = []
    for k, (px, py) in enumerate(pts):
        a = pts[max(0, k - 1)]
        b = pts[min(len(pts) - 1, k + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln * width * 0.5, dx / ln * width * 0.5
        rows.append((bm.verts.new((px + nx, py + ny, z)),
                     bm.verts.new((px - nx, py - ny, z))))
    for k in range(len(rows) - 1):
        bm.faces.new((rows[k][1], rows[k][0], rows[k + 1][0], rows[k + 1][1]))


def _bm_obj(name, bm, mat, collection, bevel=0.0):
    if not bm.faces:
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    return C._finish(C.new_mesh_obj(name, mesh), mat, collection, bevel)


def _spans_excluding(a, b, gaps):
    out, cur = [], a
    for g0, g1 in sorted(gaps):
        if g1 <= cur or g0 >= b:
            continue
        if g0 > cur:
            out.append((cur, g0))
        cur = max(cur, g1)
    if cur < b:
        out.append((cur, b))
    return out


_FONT = None


def _text_obj(body, name, size, mat, collection, loc, maxw, rot, extrude=0.010):
    """Extruded text as a real mesh (no font dependency, exports anywhere)."""
    global _FONT
    if _FONT is None:
        _FONT = bpy.data.fonts.get("Bfont Regular") or bpy.data.fonts.load("<builtin>")
    cu = bpy.data.curves.new(name + "_curve", type="FONT")
    cu.body = body
    cu.font = _FONT
    cu.size = size
    cu.extrude = extrude
    cu.resolution_u = 2
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    if not mesh.vertices:
        bpy.data.meshes.remove(mesh)
        return None
    xs = [v.co.x for v in mesh.vertices]
    bw = max(xs) - min(xs)
    s = min(1.0, maxw / bw) if bw > 1e-6 else 1.0
    obj = C.new_mesh_obj(name, mesh, loc, rot, (s, s, 1.0))
    return C._finish(obj, mat, collection)


# ---- sweeps along a ramp path ------------------------------------------------
def _sweep(name, st, ring_fn, mats, collection, split_top=False):
    bm = bmesh.new()
    rings = []
    for p in st:
        nx, ny = -p["ty"], p["tx"]
        rings.append([bm.verts.new((p["x"] + nx * l, p["y"] + ny * l, p["z"] + dz))
                      for (l, dz) in ring_fn(p)])
    n = len(rings[0])
    for k in range(len(rings) - 1):
        a, b = rings[k], rings[k + 1]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = C.new_mesh_obj(name, mesh)
    C.link_object(obj, collection)
    for m in mats:
        obj.data.materials.append(C.M(m))
    if split_top and len(mats) > 1:
        for poly in obj.data.polygons:
            poly.material_index = 0 if poly.normal.z > 0.75 else 1
    return obj


def _lane_line(name, st, sgn, inset, width, dz, mat, collection, min_hw=1.6, s_from=0.0):
    """Painted line at lateral offset sgn*(hw - inset) following the ramp."""
    bm = bmesh.new()
    rows = []
    for p in st:
        if p["hw"] < min_hw or p["s"] < s_from:
            continue
        nx, ny = -p["ty"], p["tx"]
        c = sgn * (p["hw"] - inset)
        h = width * 0.5
        rows.append((bm.verts.new((p["x"] + nx * (c + h), p["y"] + ny * (c + h), p["z"] + dz)),
                     bm.verts.new((p["x"] + nx * (c - h), p["y"] + ny * (c - h), p["z"] + dz))))
    for k in range(len(rows) - 1):
        bm.faces.new((rows[k][1], rows[k][0], rows[k + 1][0], rows[k + 1][1]))
    if bm.faces:
        bm.faces.ensure_lookup_table()
        bm.normal_update()
        if bm.faces[0].normal.z < 0.0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return _bm_obj(name, bm, mat, collection)


# ---- ramp planning -----------------------------------------------------------
def _plan_ramps(plan, deck_top, width, hy, length):
    """Off-ramp (descends going east) + on-ramp (rises going east) on the city
    side, each ending on a real N-S road so they join the street network."""
    half = plan["half"]
    x0 = -length * 0.5
    y_edge = hy - width * 0.5
    y_c = y_edge - (RAMP_W * 0.5 + 3.0)
    y_end = half + 0.3
    R = y_c - y_end
    roads = plan.get("roads_x") or []
    if R < 6.0 or not roads:
        return []
    S = (deck_top - 0.06) / RAMP_GRADE
    out = []
    # off-ramp: merge point west, avenue east
    best = None
    for r in roads:
        lane_x = r["c"] - r["w"] * 0.25
        xm = lane_x - R - 6.0 - S
        if xm < x0 + 40.0 or lane_x > -x0 - 40.0:
            continue
        score = abs(xm - (-0.26 * length))
        if best is None or score < best[0]:
            best = (score, xm, lane_x)
    if best:
        out.append({"kind": "off", "sgn": 1.0, "xm": best[1], "lane_x": best[2]})
    # on-ramp: avenue west, merge point east
    best = None
    for r in roads:
        lane_x = r["c"] + r["w"] * 0.25
        xm = lane_x + R + 6.0 + S
        if xm > -x0 - 40.0 or lane_x < x0 + 40.0:
            continue
        score = abs(xm - (0.26 * length))
        if best is None or score < best[0]:
            best = (score, xm, lane_x)
    if best:
        out.append({"kind": "on", "sgn": -1.0, "xm": best[1], "lane_x": best[2]})
    for rp in out:
        rp.update({"y_edge": y_edge, "y_c": y_c, "y_end": y_end, "R": R, "S": S})
    return out


def _ramp_stations(rp, plan, deck_top):
    half = plan["half"]
    sgn, xm, y_edge, y_c, R, S = rp["sgn"], rp["xm"], rp["y_edge"], rp["y_c"], rp["R"], rp["S"]
    pts = []
    u = 0.0
    straight = S + 6.0
    while u < straight:
        pts.append(("s", u))
        u += 4.0
    pts.append(("s", straight))
    for k in range(1, 15):
        pts.append(("a", math.pi * 0.5 * k / 14.0))
    st = []
    for kind, v in pts:
        if kind == "s":
            s_here = v
            gap = 3.0 * _smooth((v - RAMP_TAPER) / 50.0)
            hw = max(0.05, RAMP_W * 0.5 * _smooth(v / RAMP_TAPER))
            x = xm + sgn * v
            y = y_edge - gap - hw
        else:
            phi = v
            x = xm + sgn * (straight + R * math.sin(phi))
            y = (y_c - R) + R * math.cos(phi)
            hw = RAMP_W * 0.5
        st.append({"x": x, "y": y, "hw": hw})
    # path length, tangents, heights
    s = 0.0
    for k, p in enumerate(st):
        if k:
            s += math.hypot(p["x"] - st[k - 1]["x"], p["y"] - st[k - 1]["y"])
        p["s"] = s
    for k, p in enumerate(st):
        a = st[max(0, k - 1)]
        b = st[min(len(st) - 1, k + 1)]
        dx, dy = b["x"] - a["x"], b["y"] - a["y"]
        ln = math.hypot(dx, dy) or 1.0
        p["tx"], p["ty"] = dx / ln, dy / ln
        g = ground_z(p["x"], p["y"], half)
        p["g"] = g
        p["z"] = max(g + 0.06, deck_top - RAMP_GRADE * p["s"])
        p["h"] = p["z"] - g
    return st


def _build_ramp(rp, plan, collection, deck_top, R):
    st = _ramp_stations(rp, plan, deck_top)
    tag = "Ramp_Off" if rp["kind"] == "off" else "Ramp_On"
    # inner side = the side facing the highway. Off: left of travel; on (mirrored): right.
    inner = 1.0 if rp["sgn"] > 0 else -1.0

    def body_ring(p):
        hw = p["hw"] + 0.18
        bot = -(p["h"] + 0.3) if p["h"] <= 2.2 else -0.95
        return [(-hw, 0.0), (hw, 0.0), (hw, bot), (-hw, bot)]

    _sweep(tag + "_Body", st, body_ring, ["asphalt", "concrete"], collection, split_top=True)

    def barrier_ring(side):
        def f(p):
            c = side * (p["hw"] - 0.1)
            return [(c - 0.30, 0.0), (c + 0.30, 0.0), (c + 0.14, 0.95), (c - 0.14, 0.95)]
        return f

    outer_st = [p for p in st if p["hw"] >= 2.0]
    inner_st = [p for p in st if p["s"] >= RAMP_TAPER + 8.0]
    if len(outer_st) > 2:
        _sweep(tag + "_Barrier_Out", outer_st, barrier_ring(-inner), ["concrete"], collection)
    if len(inner_st) > 2:
        _sweep(tag + "_Barrier_In", inner_st, barrier_ring(inner), ["concrete"], collection)
    # paint: yellow on the highway side, white on the outer edge
    _lane_line(tag + "_Line_In", st, inner, 0.75, 0.15, 0.025, "paint_yellow", collection)
    _lane_line(tag + "_Line_Out", st, -inner, 0.75, 0.15, 0.025, "paint_white", collection)
    # piers where the ramp is a real bridge, every ~16 m on straight runs
    last_s, n = -99.0, 0
    for p in st:
        if p["h"] > 2.8 and abs(p["tx"]) > 0.9 and p["s"] - last_s >= 16.0:
            last_s = p["s"]
            ht = p["h"] - 0.95
            yaw = math.atan2(p["ty"], p["tx"])
            add_cylinder("{}_Pier_{:02d}".format(tag, n), 0.65, ht,
                         loc=(p["x"], p["y"], p["g"] + ht * 0.5), radius_top=0.80,
                         mat="concrete", collection=collection, segments=14)
            add_box("{}_PierCap_{:02d}".format(tag, n), (1.5, p["hw"] * 2.0 + 0.2, 0.55),
                    loc=(p["x"], p["y"], p["z"] - 0.95 - 0.27), rot=(0, 0, yaw),
                    mat="concrete", collection=collection, bevel=0.04)
            add_box("{}_PierFoot_{:02d}".format(tag, n), (2.4, 2.4, 0.5),
                    loc=(p["x"], p["y"], p["g"] + 0.2), mat="concrete",
                    collection=collection, bevel=0.04)
            n += 1
    return st


# ---- overhead sign gantries --------------------------------------------------
_LA_DEST = ["DOWNTOWN", "HARBOR FWY", "SANTA MONICA", "LONG BEACH", "PASADENA",
            "CIVIC CENTER", "HOLLYWOOD", "LAX AIRPORT"]
_NYC_DEST = ["MIDTOWN", "BROOKLYN", "THE BRONX", "FDR DRIVE", "WALL STREET"]


def _build_gantry(idx, gx, panels, collection, hy, deck_top, width):
    """Steel box-truss spanning the deck on two posts at the barrier line, with
    green sign panels (white border + legend) facing eastbound traffic (-X)."""
    steel = bmesh.new()
    lamps = bmesh.new()
    half_w = width * 0.5 - 0.55            # posts sit on the barrier line
    z_lo, z_hi = deck_top + 6.7, deck_top + 7.7
    for s in (-1, 1):
        _bm_cube(steel, (gx, hy + s * half_w, deck_top + 4.45), (0.45, 0.45, 6.9))
        _bm_cube(steel, (gx, hy + s * half_w, deck_top + 1.06), (0.9, 0.9, 0.12))
    L = 2.0 * half_w
    for z in (z_lo, z_hi):
        _bm_cube(steel, (gx, hy, z), (0.16, L, 0.16))
    bays = 12
    dy = L / bays
    for i in range(bays + 1):
        _bm_cube(steel, (gx, hy - half_w + i * dy, (z_lo + z_hi) * 0.5), (0.09, 0.09, z_hi - z_lo))
    for i in range(bays):
        yc = hy - half_w + (i + 0.5) * dy
        ang = math.atan2(z_hi - z_lo, dy) * (1.0 if i % 2 == 0 else -1.0)
        _bm_cube(steel, (gx, yc, (z_lo + z_hi) * 0.5),
                 (0.08, math.hypot(dy, z_hi - z_lo), 0.08), rot=(ang, 0.0, 0.0))
    # lay panels out left (+y) to right (-y)
    gap = 0.9
    total = sum(p["w"] for p in panels) + gap * (len(panels) - 1)
    k = min(1.0, (2.0 * half_w - 1.2) / total)
    y = hy + total * k * 0.5
    zc = deck_top + 6.95
    H = 2.5
    face = (math.pi * 0.5, 0.0, -math.pi * 0.5)       # text/plane faces -X
    for pi, pn in enumerate(panels):
        w = pn["w"] * k
        yc = y - w * 0.5
        y -= w + gap * k
        add_box("Gantry_{:02d}_Back_{}".format(idx, pi), (0.06, w, H),
                loc=(gx - 0.30, yc, zc), mat="paint_white", collection=collection)
        add_box("Gantry_{:02d}_Panel_{}".format(idx, pi), (0.03, w - 0.30, H - 0.30),
                loc=(gx - 0.345, yc, zc), mat="paint_green", collection=collection)
        for dz in (-0.9, 0.9):
            _bm_cube(steel, (gx - 0.20, yc, zc + dz), (0.10, w * 0.96, 0.08))
        for sy in (-0.28, 0.28):
            _bm_cube(steel, (gx - 0.55, yc + w * sy, deck_top + 8.45), (0.70, 0.05, 0.05))
            _bm_cube(lamps, (gx - 0.95, yc + w * sy, deck_top + 8.45), (0.55, 0.32, 0.14))
        lines = pn["lines"]
        arrow = pn.get("arrow")
        xt = gx - 0.375
        if arrow:
            ys = [zc + 0.62, zc + 0.08]
        else:
            ys = [zc + 0.45, zc - 0.40] if len(lines) > 1 else [zc]
        sizes = [0.55, 0.42]
        for li, body in enumerate(lines[:2]):
            _text_obj(body, "Gantry_{:02d}_Text_{}_{}".format(idx, pi, li), sizes[li],
                      "paint_white", collection, (xt, yc, ys[li]), w - 0.9, face)
        if arrow:
            ab = bmesh.new()
            xa = gx - 0.372
            zt, zb = zc - 0.30, zc - 1.05
            pts = [(0.14, zt), (0.14, zt - 0.38), (0.48, zt - 0.38), (0.0, zb),
                   (-0.48, zt - 0.38), (-0.14, zt - 0.38), (-0.14, zt)]
            vs = [ab.verts.new((xa, yc + py, pz)) for py, pz in pts]
            ab.faces.new(vs)
            _bm_obj("Gantry_{:02d}_Arrow_{}".format(idx, pi), ab, "paint_white", collection)
    _bm_obj("Gantry_{:02d}_Steel".format(idx), steel, "metal_galv", collection)
    _bm_obj("Gantry_{:02d}_Lamps".format(idx), lamps, "metal_dark", collection)


def _panel_width(lines):
    return max(4.2, min(8.4, max(len(s) for s in lines) * 0.44 + 1.4))


# ---- main highway builder ----------------------------------------------------
def build_highway(plan, collection):
    half = plan["half"]
    hy = plan["highway_y"]
    deck_top = 9.0
    deck_t = 1.10
    width = 21.0
    length = half * 2.0 + 260.0
    x0 = -length * 0.5
    R = C.rng("highway")
    la = C.is_la()

    ramps = _plan_ramps(plan, deck_top, width, hy, length)
    gaps = []
    for rp in ramps:
        if rp["kind"] == "off":
            gaps.append((rp["xm"] - 3.0, rp["xm"] + RAMP_TAPER + 3.0))
        else:
            gaps.append((rp["xm"] - RAMP_TAPER - 3.0, rp["xm"] + 3.0))

    add_box("Highway_Deck", (length, width, deck_t),
            loc=(0.0, hy, deck_top - deck_t * 0.5), mat="asphalt",
            collection=collection, bevel=0.04)

    # fascia beams
    for s in (-1, 1):
        add_box("Highway_Fascia_{}".format("N" if s > 0 else "S"),
                (length, 0.45, 0.85),
                loc=(0.0, hy + s * (width * 0.5 - 0.10), deck_top - 0.55),
                mat="concrete", collection=collection, bevel=0.02)

    # concrete barriers (the city-side one is cut where a ramp joins)
    for s in (-1, 1):
        spans = _spans_excluding(x0, -x0, gaps) if s < 0 else [(x0, -x0)]
        for bi, (a, b) in enumerate(spans):
            add_box("Highway_Barrier_{}_{:02d}".format("N" if s > 0 else "S", bi),
                    (b - a, 0.55, 1.05),
                    loc=((a + b) * 0.5, hy + s * (width * 0.5 - 0.55), deck_top + 0.52),
                    mat="concrete", collection=collection, bevel=0.04)

    # lamp masts on the median barrier line
    for i in range(14):
        x = x0 + 30.0 + i * (length - 60.0) / 13.0
        add_cylinder("Highway_Mast_{:02d}".format(i), 0.12, 8.0,
                     loc=(x, hy + width * 0.5 - 1.2, deck_top + 4.0),
                     mat="metal_galv", collection=collection, segments=10)
        add_box("Highway_MastArm_{:02d}".format(i), (2.1, 0.14, 0.14),
                loc=(x - 1.0, hy + width * 0.5 - 1.2, deck_top + 8.0),
                mat="metal_galv", collection=collection)
        add_box("Highway_MastHead_{:02d}".format(i), (0.75, 0.30, 0.16),
                loc=(x - 2.0, hy + width * 0.5 - 1.2, deck_top + 7.95),
                mat="metal_dark", collection=collection)

    # ---- bents: runs of one engineering family, jittered spans, LA favours
    # round columns (Caltrans-style), NYC favours wall piers + hammerheads
    fams = ["round2", "round1", "wall"] if la else ["wall", "hammer", "round2"]
    wts = [0.45, 0.30, 0.25] if la else [0.55, 0.30, 0.15]
    under = deck_top - deck_t
    pier_x = x0 + R.uniform(18.0, 26.0)
    idx, run_left, fam = 0, 0, "wall"
    while pier_x < -x0 - 20.0:
        if run_left <= 0:
            fam = R.choices(fams, wts)[0]
            run_left = R.randint(4, 8)
        run_left -= 1
        gz = ground_z(pier_x, hy, half)
        ph = under - gz
        if ph > 0.8:
            n = "{:03d}".format(idx)
            if fam == "round2":
                for s in (-1, 1):
                    add_cylinder("Highway_Pier_{}_{}".format(n, "N" if s > 0 else "S"), 0.85, ph - 0.9,
                                 loc=(pier_x, hy + s * 5.4, gz + (ph - 0.9) * 0.5), radius_top=1.0,
                                 mat="concrete", collection=collection, segments=16)
                    add_box("Highway_PierFoot_{}_{}".format(n, "N" if s > 0 else "S"), (2.6, 2.6, 0.6),
                            loc=(pier_x, hy + s * 5.4, gz + 0.27), mat="concrete",
                            collection=collection, bevel=0.05)
                add_box("Highway_PierCap_" + n, (1.9, width - 1.6, 0.9),
                        loc=(pier_x, hy, under - 0.46), mat="concrete",
                        collection=collection, bevel=0.05)
            elif fam == "round1":
                add_cylinder("Highway_Pier_" + n, 1.15, ph - 1.0,
                             loc=(pier_x, hy, gz + (ph - 1.0) * 0.5), radius_top=1.45,
                             mat="concrete", collection=collection, segments=20)
                add_box("Highway_PierCap_" + n, (2.6, width - 2.0, 1.0),
                        loc=(pier_x, hy, under - 0.51), mat="concrete",
                        collection=collection, bevel=0.06)
                add_box("Highway_PierFoot_" + n, (3.6, 3.6, 0.6),
                        loc=(pier_x, hy, gz + 0.27), mat="concrete",
                        collection=collection, bevel=0.05)
            elif fam == "hammer":
                add_box("Highway_Pier_" + n, (1.6, 2.4, ph - 1.2),
                        loc=(pier_x, hy, gz + (ph - 1.2) * 0.5), mat="concrete",
                        collection=collection, bevel=0.05)
                add_box("Highway_PierCap_" + n, (2.2, width - 1.2, 1.2),
                        loc=(pier_x, hy, under - 0.61), mat="concrete",
                        collection=collection, bevel=0.06)
                add_box("Highway_PierFoot_" + n, (3.0, 3.8, 0.55),
                        loc=(pier_x, hy, gz + 0.27), mat="concrete",
                        collection=collection, bevel=0.05)
            else:
                add_box("Highway_Pier_" + n, (1.8, 3.0, ph),
                        loc=(pier_x, hy, gz + ph * 0.5), mat="concrete",
                        collection=collection, bevel=0.05)
                add_box("Highway_PierCap_" + n, (2.4, width - 2.0, 0.65),
                        loc=(pier_x, hy, under - 0.33), mat="concrete",
                        collection=collection, bevel=0.04)
                add_box("Highway_PierFoot_" + n, (3.2, 4.4, 0.55),
                        loc=(pier_x, hy, gz + 0.27), mat="concrete",
                        collection=collection, bevel=0.05)
        pier_x += R.uniform(23.0, 29.0)
        idx += 1

    # ---- expansion joints: jittered spacing, plain plates + finger joints
    plates = bmesh.new()
    fingers = bmesh.new()
    seals = bmesh.new()
    jx = x0 + R.uniform(8.0, 14.0)
    while jx < -x0 - 12.0:
        _bm_cube(plates, (jx, hy, deck_top + 0.01), (R.uniform(0.18, 0.28), width - 1.2, 0.06))
        if R.random() < 0.5:                      # finger-plate joint: two interleaved combs
            pitch = 0.5
            n_t = int((width - 1.6) / pitch)
            for t in range(n_t):
                ty = hy - (n_t - 1) * pitch * 0.5 + t * pitch
                _bm_cube(fingers, (jx + (0.17 if t % 2 else -0.17), ty, deck_top + 0.035),
                         (0.34, 0.26, 0.03))
        if R.random() < 0.35:                     # bituminous repair strip beside the joint
            _bm_cube(seals, (jx + R.choice((-1, 1)) * 0.55, hy, deck_top + 0.006),
                     (0.5, width - 1.4, 0.012))
        jx += R.uniform(10.0, 15.0)
    _bm_obj("Highway_Joints", plates, "metal_dark", collection)
    _bm_obj("Highway_FingerJoints", fingers, "metal", collection)
    _bm_obj("Highway_JointSeals", seals, "asphalt_patch", collection)

    # ---- surface wear: wheel tracks, patches, tar-snake cracks
    wear = bmesh.new()
    for lc in (-7.3, -2.6, 2.6, 7.3):
        for off in (-0.85, 0.85):
            x = x0 + R.uniform(4.0, 12.0)
            while x < -x0 - 12.0:
                seg = R.uniform(15.0, 50.0)
                b = min(x + seg, -x0 - 6.0)
                _bm_strip(wear, [(x, hy + lc + off), (b, hy + lc + off)], R.uniform(0.45, 0.6), deck_top + 0.004)
                x = b + R.uniform(3.0, 14.0)
    _bm_obj("Highway_WheelWear", wear, "asphalt_patch", collection)

    patches = bmesh.new()
    for _ in range(int(length / 14.0)):
        px = R.uniform(x0 + 10.0, -x0 - 10.0)
        py = hy + R.uniform(-8.8, 8.8)
        pw, pl = R.uniform(1.2, 3.4), R.uniform(1.0, 3.8)
        _bm_cube(patches, (px, py, deck_top + 0.007), (pw, pl, 0.004), rot=(0, 0, R.uniform(-0.05, 0.05)))
    _bm_obj("Highway_Patches", patches, "asphalt_patch", collection)

    cracks = bmesh.new()
    for _ in range(int(length / 28.0)):
        cx = R.uniform(x0 + 10.0, -x0 - 10.0)
        cy = hy + R.uniform(-8.5, 8.5)
        ang = R.uniform(0.0, math.pi)
        pts = []
        for k in range(9):
            ang += R.uniform(-0.45, 0.45)
            pts.append((cx + k * 0.7 * math.cos(ang), cy + k * 0.7 * math.sin(ang)))
        _bm_strip(cracks, pts, 0.035, deck_top + 0.010)
    _bm_obj("Highway_Cracks", cracks, "paint_black", collection)

    # ---- lane markings: dashed white between lanes, solid edge lines
    for lane_y in (-5.25, 5.25):
        d = 0
        dx = x0 + 6.0
        while dx < -x0 - 6.0:
            add_plane("Highway_Dash_{}_{:03d}".format("N" if lane_y > 0 else "S", d),
                      (3.0, 0.15), loc=(dx, hy + lane_y, deck_top + 0.012),
                      mat="paint_white", collection=collection)
            dx += 9.0
            d += 1
    for edge_y in (-width * 0.5 + 1.1, width * 0.5 - 1.1):
        north = edge_y > 0
        spans = [(x0 + 2.0, -x0 - 2.0)] if north else _spans_excluding(x0 + 2.0, -x0 - 2.0, gaps)
        for ei, (a, b) in enumerate(spans):
            add_plane("Highway_EdgeLine_{}_{:02d}".format("N" if north else "S", ei),
                      (b - a, 0.20), loc=((a + b) * 0.5, hy + edge_y, deck_top + 0.012),
                      mat="paint_white", collection=collection)
    for gi, (a, b) in enumerate(gaps):            # broken edge line across a ramp opening
        xx = a + 1.0
        while xx < b - 3.0:
            add_plane("Highway_RampDash_{:02d}_{:02d}".format(gi, int(xx - a)), (3.0, 0.20),
                      loc=(xx + 1.5, hy - width * 0.5 + 1.1, deck_top + 0.012),
                      mat="paint_white", collection=collection)
            xx += 9.0

    # guard-rail posts along the outer fascia (cut at ramp openings)
    px = x0
    pi_ = 0
    while px < -x0:
        if not any(g0 <= px <= g1 for g0, g1 in gaps):
            add_box("Highway_Post_{:03d}".format(pi_), (0.10, 0.10, 0.75),
                    loc=(px, hy - width * 0.5 - 0.12, deck_top + 0.37),
                    mat="metal_galv", collection=collection)
        px += 3.0
        pi_ += 1

    # ---- ramps
    ramp_info = []
    for rp in ramps:
        _build_ramp(rp, plan, collection, deck_top, R)
        ramp_info.append({"kind": rp["kind"], "x_merge": round(rp["xm"], 1)})

    # ---- overhead sign gantries: advance + exit for the off-ramp, one more
    # ahead of the on-ramp merge; a generic pair when no ramps fit
    dest = list(_LA_DEST if la else _NYC_DEST)
    R.shuffle(dest)
    gantries = []
    off = next((r for r in ramps if r["kind"] == "off"), None)
    on = next((r for r in ramps if r["kind"] == "on"), None)
    if off:
        gantries.append((off["xm"] - 150.0, [
            {"lines": [dest[0], "1 MILE"]}, {"lines": [dest[1], "EXIT 14"]}], False))
        gantries.append((off["xm"] - 28.0, [
            {"lines": [dest[2], "NEXT 2 EXITS"]},
            {"lines": ["EXIT 14", dest[0]], "arrow": True}], True))
    if on:
        gantries.append((on["xm"] - 120.0, [
            {"lines": [dest[3 % len(dest)], "3 MILES"]}], False))
    if not gantries:
        gantries = [(-0.25 * length, [{"lines": [dest[0], "1 MILE"]}], False),
                    (0.25 * length, [{"lines": [dest[1], "2 MILES"]}], False)]
    gi = 0
    for gx, panels, _exit in gantries:
        if gx < x0 + 25.0 or gx > -x0 - 25.0:
            continue
        for pn in panels:
            pn["w"] = _panel_width(pn["lines"])
        _build_gantry(gi, gx, panels, collection, hy, deck_top, width)
        gi += 1

    C.set_asset("highway_y", hy)
    C.set_asset("highway_deck_z", deck_top)
    C.set_asset("highway_ramps", ramp_info)
    print("  highway: {} bents, {} ramps, {} gantries".format(idx, len(ramps), gi))


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
def build():
    plan = plan_city()
    collection = C.col("CITY_Terrain")
    build_ground(plan, collection)
    build_block_lots(plan, collection)
    build_waterfront(plan, collection)
    build_highway(plan, collection)
    return plan


if __name__ == "__main__":
    C.bootstrap(banner="M1 TERRAIN")
    C.build_all_materials()
    p = build()
    C.report()
    print("  terrain built: {} blocks, river at y={:.1f}, highway at y={:.1f}".format(
        len(p["blocks"]), p["water_y"], p["highway_y"]))
