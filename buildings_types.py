# =============================================================================
#  CITY BUILD  --  M5 : BUILDING TYPES & PLACEMENT
#  standalone:  blender -b -P buildings_types.py -- --quality preview
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
from core import CONFIG, U, rng, add_box, add_plane, add_cylinder, plan_city
import buildings_core as BC
from buildings_core import emit_building, STYLES, pick_style, BASE_Z, FLOOR_H, GROUND_H

SW = 3.20
SIDEWALK = SW


# -----------------------------------------------------------------------------
# bmesh helpers
# -----------------------------------------------------------------------------
def _box_bm(bm, cx, cy, cz, sx, sy, sz, rot=0.0):
    ca, sa = math.cos(rot), math.sin(rot)
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    bot, top = [], []
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


def _gable_bm(bm, cx, cy, cz, sx, sy, sz, rot=0.0):
    """Triangular prism roof, ridge running along local X."""
    ca, sa = math.cos(rot), math.sin(rot)

    def P(px, py, pz):
        return bm.verts.new((cx + px * ca - py * sa,
                             cy + px * sa + py * ca, cz + pz))

    hx, hy = sx * 0.5, sy * 0.5
    a = P(-hx, -hy, 0.0)
    b = P(hx, -hy, 0.0)
    c = P(hx, hy, 0.0)
    d = P(-hx, hy, 0.0)
    e = P(-hx, 0.0, sz)
    f = P(hx, 0.0, sz)
    bm.faces.new((a, b, f, e))
    bm.faces.new((d, c, f, e))
    bm.faces.new((a, d, e))
    bm.faces.new((b, c, f))
    bm.faces.new((a, b, c, d))


def _mesh(name, bm, mat, collection):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    C.link_object(ob, collection)
    if mat:
        ob.data.materials.append(C.M(mat))
    return ob


# -----------------------------------------------------------------------------
# lot helpers
# -----------------------------------------------------------------------------
def _inner(b):
    return (b["x0"] + SIDEWALK, b["y0"] + SIDEWALK,
            b["x1"] - SIDEWALK, b["y1"] - SIDEWALK)


def _split_x(rect, n):
    x0, y0, x1, y1 = rect
    w = (x1 - x0) / n
    return [(x0 + w * i, y0, x0 + w * (i + 1), y1) for i in range(n)]


def _split_y(rect, n):
    x0, y0, x1, y1 = rect
    h = (y1 - y0) / n
    return [(x0, y0 + h * i, x1, y0 + h * (i + 1)) for i in range(n)]


def _row(rect, n, depth, side="S"):
    x0, y0, x1, y1 = rect
    out = []
    w = (x1 - x0) / n
    for i in range(n):
        a = x0 + w * i
        b = x0 + w * (i + 1)
        if side == "S":
            out.append((a, y0, b, y0 + depth))
        else:
            out.append((a, y1 - depth, b, y1))
    return out


# -----------------------------------------------------------------------------
# type builders
# -----------------------------------------------------------------------------
def townhouse(name, rect, R, collection, detail):
    x0, y0, x1, y1 = rect
    w = x1 - x0
    h = y1 - y0
    floors = R.randint(2, 4)
    height = floors * FLOOR_H + 0.6
    style = R.choice(["brick_old", "plaster", "plaster_pink", "plaster_teal",
                      "brick_modern", "stone_old"])
    res = emit_building(name, rect, height, style, collection, R,
                        detail=detail, ground_floor=True)
    # stoop: steps down to the sidewalk on the south face
    bm = bmesh.new()
    steps = R.randint(3, 5)
    sw_ = min(1.8, w * 0.45)
    for i in range(steps):
        _box_bm(bm, (x0 + x1) * 0.5, y0 - 0.30 - i * 0.30,
                BASE_Z + 0.09 * (steps - i), sw_, 0.32, 0.18 * (steps - i) + 0.06)
    _mesh(name + "_Stoop", bm, "stone", collection)
    # front door canopy
    add_box(name + "_DoorCanopy", (sw_ + 0.4, 0.9, 0.10),
            loc=((x0 + x1) * 0.5, y0 - 0.45, BASE_Z + 2.55),
            mat="metal_dark", collection=collection)
    return res


def midrise(name, rect, R, collection, detail):
    floors = R.randint(4, 8)
    height = floors * FLOOR_H + GROUND_H * 0.5
    style = R.choice(["brick_old", "brick_modern", "plaster", "concrete_panel",
                      "stone_old"])
    return emit_building(name, rect, height, style, collection, R, detail=detail)


def tower(name, rect, R, collection, detail):
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    w, h = x1 - x0, y1 - y0
    total = R.uniform(45.0, 125.0)
    tiers = R.randint(2, 3)
    style = R.choice(["curtain", "curtain", "concrete_panel", "stone_old"])
    base = BASE_Z
    remaining = total
    out = None
    inset = 0.0
    for t in range(tiers):
        frac = 1.0 / (tiers - t) if tiers - t > 0 else 1.0
        th = remaining * (0.55 if t < tiers - 1 else 1.0)
        th = max(12.0, th)
        rect_t = (x0 + inset, y0 + inset, x1 - inset, y1 - inset)
        if rect_t[2] - rect_t[0] < 6.0 or rect_t[3] - rect_t[1] < 6.0:
            break
        out = emit_building("{}_T{}".format(name, t), rect_t, th, style,
                            collection, R, base_z=base, detail=detail,
                            ground_floor=(t == 0))
        base += th
        remaining -= th
        inset += R.uniform(1.2, 2.6)
        if remaining < 10.0:
            break
    return out


def warehouse(name, rect, R, collection, detail):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    height = R.uniform(7.5, 14.0)
    style = R.choice(["industrial", "warehouse"])
    res = emit_building(name, rect, height, style, collection, R,
                        detail=detail, ground_floor=False)
    bm = bmesh.new()
    # loading dock platform along the south face
    _box_bm(bm, (x0 + x1) * 0.5, y0 - 1.1, BASE_Z + 0.55, w * 0.9, 2.2, 1.1)
    # roll-up doors
    n = max(1, int(w / 6.0))
    for i in range(n):
        dx = x0 + (i + 0.5) * w / n
        _box_bm(bm, dx, y0 - 0.06, BASE_Z + 2.2, 3.4, 0.12, 3.6)
    _mesh(name + "_Dock", bm, "metal_dark", collection)
    # roof vents
    for i in range(R.randint(2, 5)):
        add_cylinder("{}_Vent{}".format(name, i), 0.35, 0.9,
                     loc=(R.uniform(x0 + 2, x1 - 2), R.uniform(y0 + 2, y1 - 2),
                          BASE_Z + height + 0.45),
                     mat="metal_galv", collection=collection, segments=10)
    return res


def church(name, rect, R, collection, detail):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    nave_h = R.uniform(9.0, 13.0)
    res = emit_building(name, rect, nave_h, "stone_old", collection, R,
                        detail=detail, ground_floor=True)
    bm = bmesh.new()
    _gable_bm(bm, (x0 + x1) * 0.5, (y0 + y1) * 0.5, BASE_Z + nave_h,
              w + 0.6, h + 0.6, w * 0.42)
    _mesh(name + "_Roof", bm, "stone_dark", collection)
    # bell tower on one corner
    tw = min(5.0, w * 0.3)
    tx = x0 + tw * 0.5 + 0.4
    ty = y0 + tw * 0.5 + 0.4
    add_box(name + "_Tower", (tw, tw, nave_h + 7.0),
            loc=(tx, ty, BASE_Z + (nave_h + 7.0) * 0.5),
            mat="stone", collection=collection, bevel=0.04)
    add_cylinder(name + "_Spire", tw * 0.62, 6.0,
                 loc=(tx, ty, BASE_Z + nave_h + 7.0 + 3.0),
                 mat="copper_patina", collection=collection, segments=8,
                 radius_top=0.05)
    return res


def parking_garage(name, rect, R, collection, detail):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    levels = R.randint(3, 6)
    deck_h = 3.2
    bm = bmesh.new()
    for i in range(levels + 1):
        _box_bm(bm, cx, cy, BASE_Z + 0.15 + i * deck_h, w, h, 0.30)
    # spandrel panels on the perimeter
    for i in range(levels):
        z = BASE_Z + 0.15 + i * deck_h + 0.95
        _box_bm(bm, cx, y0 + 0.12, z, w, 0.24, 1.30)
        _box_bm(bm, cx, y1 - 0.12, z, w, 0.24, 1.30)
        _box_bm(bm, x0 + 0.12, cy, z, 0.24, h, 1.30)
        _box_bm(bm, x1 - 0.12, cy, z, 0.24, h, 1.30)
    _mesh(name + "_Decks", bm, "concrete", collection)
    # columns
    bm2 = bmesh.new()
    nx = max(2, int(w / 7.0))
    ny = max(2, int(h / 7.0))
    for i in range(nx + 1):
        for j in range(ny + 1):
            px = x0 + (w) * i / nx
            py = y0 + (h) * j / ny
            _box_bm(bm2, px, py, BASE_Z + levels * deck_h * 0.5,
                    0.55, 0.55, levels * deck_h)
    _mesh(name + "_Columns", bm2, "concrete", collection)
    # stair / lift core
    add_box(name + "_Core", (4.2, 5.0, levels * deck_h + 2.4),
            loc=(x0 + 3.0, y1 - 3.4, BASE_Z + (levels * deck_h + 2.4) * 0.5),
            mat="brick_old", collection=collection, bevel=0.03)
    return {"name": name, "rect": rect, "height": levels * deck_h + 2.4,
            "style": "concrete_panel", "objects": [], "floors": levels}


def gas_station(name, rect, R, collection, detail):
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    # shop
    shop = (x0 + 1.0, y1 - 8.0, x1 - 1.0, y1 - 1.0)
    emit_building(name + "_Shop", shop, 4.2, "concrete_panel", collection, R,
                  detail=detail, ground_floor=True)
    # canopy
    bm = bmesh.new()
    cw, ch = w * 0.62, h * 0.42
    ccx, ccy = cx, y0 + ch * 0.5 + 1.5
    _box_bm(bm, ccx, ccy, BASE_Z + 5.2, cw, ch, 0.55)
    _box_bm(bm, ccx, ccy, BASE_Z + 4.85, cw * 0.96, ch * 0.94, 0.18)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _box_bm(bm, ccx + sx * cw * 0.42, ccy + sy * ch * 0.38,
                    BASE_Z + 2.4, 0.42, 0.42, 4.8)
    _mesh(name + "_Canopy", bm, "metal_dark", collection)
    # pumps
    for i in range(3):
        px = ccx - cw * 0.28 + i * cw * 0.28
        add_box("{}_Pump{}".format(name, i), (0.85, 0.55, 1.75),
                loc=(px, ccy, BASE_Z + 0.88), mat="metal_galv",
                collection=collection, bevel=0.03)
        add_box("{}_PumpTop{}".format(name, i), (0.95, 0.62, 0.28),
                loc=(px, ccy, BASE_Z + 1.90), mat="car_paint_red",
                collection=collection, bevel=0.02)
    # price sign pylon
    add_box(name + "_Pylon", (0.9, 0.9, 7.5),
            loc=(x0 + 1.6, y0 + 1.6, BASE_Z + 3.75),
            mat="metal_galv", collection=collection)
    add_box(name + "_PriceSign", (3.4, 0.35, 2.4),
            loc=(x0 + 1.6, y0 + 1.6, BASE_Z + 8.2),
            mat="car_paint_white", collection=collection, bevel=0.03)
    return {"name": name, "rect": rect, "height": 9.0, "style": "concrete_panel",
            "objects": [], "floors": 1}


def small_shop(name, rect, R, collection, detail, style="concrete_panel",
               height=4.6, sign_color="neon_red"):
    res = emit_building(name, rect, height, style, collection, R,
                        detail=detail, ground_floor=True)
    x0, y0, x1, y1 = rect
    add_box(name + "_BladeSign", (0.18, 1.5, 1.5),
            loc=(x1 + 0.12, (y0 + y1) * 0.5, BASE_Z + height - 1.2),
            mat=sign_color, collection=collection)
    return res


def motel(name, rect, R, collection, detail):
    x0, y0, x1, y1 = rect
    w = x1 - x0
    depth = min(12.0, (y1 - y0) * 0.5)
    body = (x0, y0, x1, y0 + depth)
    res = emit_building(name, body, 7.0, "plaster_pink", collection, R,
                        detail=detail, ground_floor=True)
    # walkway canopy + doors
    bm = bmesh.new()
    n = max(3, int(w / 4.0))
    for i in range(n):
        dx = x0 + (i + 0.5) * w / n
        _box_bm(bm, dx, y0 - 0.06, BASE_Z + 1.05, 1.05, 0.12, 2.10)
        _box_bm(bm, dx, y0 - 1.3, BASE_Z + 2.75, 3.4, 2.4, 0.12)
    _mesh(name + "_Walkway", bm, "metal_dark", collection)
    add_box(name + "_Office", (6.0, 5.0, 3.6),
            loc=(x0 + 4.0, y1 - 3.0, BASE_Z + 1.8),
            mat="plaster", collection=collection, bevel=0.03)
    return res


def bank(name, rect, R, collection, detail):
    res = emit_building(name, rect, 15.0, "stone_old", collection, R,
                        detail=detail, ground_floor=True)
    x0, y0, x1, y1 = rect
    bm = bmesh.new()
    n = 4
    for i in range(n):
        px = x0 + (i + 0.5) * (x1 - x0) / n
        _box_bm(bm, px, y0 - 0.55, BASE_Z + 4.6, 0.85, 0.85, 9.2)
    _box_bm(bm, (x0 + x1) * 0.5, y0 - 0.55, BASE_Z + 9.4,
            (x1 - x0) * 0.94, 1.5, 0.7)
    _mesh(name + "_Colonnade", bm, "stone", collection)
    return res


def hotel(name, rect, R, collection, detail):
    floors = R.randint(8, 16)
    height = floors * FLOOR_H
    res = emit_building(name, rect, height, R.choice(["brick_old", "stone_old"]),
                        collection, R, detail=detail)
    x0, y0, x1, y1 = rect
    add_box(name + "_VerticalSign", (1.2, 0.35, 6.0),
            loc=(x1 + 0.2, (y0 + y1) * 0.5, BASE_Z + height * 0.55),
            mat="neon_red", collection=collection)
    return res


def school(name, rect, R, collection, detail):
    res = emit_building(name, rect, 12.0, "brick_pale", collection, R,
                        detail=detail, ground_floor=True)
    x0, y0, x1, y1 = rect
    add_box(name + "_Gym", ((x1 - x0) * 0.45, (y1 - y0) * 0.55, 8.0),
            loc=(x0 + (x1 - x0) * 0.28, y1 - (y1 - y0) * 0.3, BASE_Z + 4.0),
            mat="brick_dark", collection=collection, bevel=0.03)
    return res


def civic(name, rect, R, collection, detail, wall="stone", floors=3,
          garage=False):
    height = floors * FLOOR_H + 1.0
    res = emit_building(name, rect, height, "stone_old" if wall == "stone" else "brick_old",
                        collection, R, detail=detail, ground_floor=True)
    if garage:
        x0, y0, x1, y1 = rect
        bm = bmesh.new()
        for i in range(2):
            _box_bm(bm, x0 + (i + 0.5) * (x1 - x0) / 2.0, y0 - 0.06,
                    BASE_Z + 2.1, 4.2, 0.14, 4.2)
        _mesh(name + "_GarageDoors", bm, "metal_dark", collection)
    return res


def subway_entrance(name, rect, R, collection):
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    w = x1 - x0
    bm = bmesh.new()
    # stair void
    _box_bm(bm, cx, cy, BASE_Z - 0.6, w * 0.62, 3.0, 1.2)
    # side walls
    _box_bm(bm, cx - w * 0.31, cy, BASE_Z + 0.55, 0.22, 3.2, 1.1)
    _box_bm(bm, cx + w * 0.31, cy, BASE_Z + 0.55, 0.22, 3.2, 1.1)
    # railings
    for sgn in (-1, 1):
        _box_bm(bm, cx + sgn * w * 0.31, cy, BASE_Z + 1.15, 0.06, 3.2, 0.06)
    _mesh(name + "_Stair", bm, "metal_dark", collection)
    # globe lamps + sign
    for sgn in (-1, 1):
        add_cylinder("{}_GlobePole{}".format(name, sgn), 0.06, 2.6,
                     loc=(cx + sgn * w * 0.36, cy - 1.9, BASE_Z + 1.3),
                     mat="metal_dark", collection=collection, segments=8)
        add_cylinder("{}_Globe{}".format(name, sgn), 0.22, 0.30,
                     loc=(cx + sgn * w * 0.36, cy - 1.9, BASE_Z + 2.75),
                     mat="lamp_warm", collection=collection, segments=10)
    return {"name": name, "rect": rect, "height": 1.2, "style": "metal_dark",
            "objects": [], "floors": 0}


# -----------------------------------------------------------------------------
# placement
# -----------------------------------------------------------------------------
def build():
    plan = plan_city()
    collection = C.col("CITY_Buildings")
    R = rng("buildings_types")
    detail = 1.0 if CONFIG["quality"] == "high" else 0.62
    placed = []
    density = CONFIG["density"]

    for bi, b in enumerate(plan["blocks"]):
        dist = b["district"]
        if dist == "parkland":
            continue
        inner = _inner(b)
        iw = inner[2] - inner[0]
        ih = inner[3] - inner[1]
        if iw < 8.0 or ih < 8.0:
            continue

        if dist == "downtown":
            if R.random() > density:
                continue
            n = 1 if iw * ih < 2600 else 2
            rects = _split_x(inner, n) if iw >= ih else _split_y(inner, n)
            for k, r in enumerate(rects):
                if r[2] - r[0] < 10.0 or r[3] - r[1] < 10.0:
                    continue
                placed.append(tower("Tower_{}_{}".format(bi, k), r, R,
                                    collection, detail))

        elif dist == "midtown":
            if R.random() > density:
                continue
            n = R.choice([2, 2, 3])
            rects = _split_x(inner, n) if iw >= ih else _split_y(inner, n)
            for k, r in enumerate(rects):
                if r[2] - r[0] < 7.0 or r[3] - r[1] < 7.0:
                    continue
                roll = R.random()
                if roll < 0.18:
                    placed.append(parking_garage("Garage_{}_{}".format(bi, k), r, R, collection, detail))
                elif roll < 0.30:
                    placed.append(small_shop("Shop_{}_{}".format(bi, k), r, R, collection, detail))
                elif roll < 0.38:
                    placed.append(hotel("Hotel_{}_{}".format(bi, k), r, R, collection, detail))
                else:
                    placed.append(midrise("Mid_{}_{}".format(bi, k), r, R, collection, detail))

        elif dist == "residential":
            if R.random() > density:
                continue
            n = max(2, int(iw / 7.5))
            lots = _row(inner, n, min(ih * 0.55, 15.0), "S")
            for k, r in enumerate(lots):
                if r[2] - r[0] < 4.2:
                    continue
                placed.append(townhouse("TH_{}_{}".format(bi, k), r, R, collection, detail))
            # a midrise at the back of some blocks
            if ih > 26.0 and R.random() < 0.55:
                back = (inner[0], inner[1] + min(ih * 0.55, 15.0) + 1.0,
                        inner[2], inner[3])
                if back[3] - back[1] > 8.0:
                    placed.append(midrise("MidBack_{}".format(bi), back, R, collection, detail))

        elif dist == "industrial":
            if R.random() > density:
                continue
            n = 1 if iw * ih < 3000 else 2
            rects = _split_x(inner, n) if iw >= ih else _split_y(inner, n)
            for k, r in enumerate(rects):
                if r[2] - r[0] < 12.0 or r[3] - r[1] < 12.0:
                    continue
                roll = R.random()
                if roll < 0.22:
                    placed.append(gas_station("Gas_{}_{}".format(bi, k), r, R, collection, detail))
                elif roll < 0.34:
                    placed.append(warehouse("Depot_{}_{}".format(bi, k), r, R, collection, detail))
                else:
                    placed.append(warehouse("Ind_{}_{}".format(bi, k), r, R, collection, detail))

        elif dist == "waterfront":
            if R.random() > density:
                continue
            n = R.choice([1, 2])
            rects = _split_x(inner, n) if iw >= ih else _split_y(inner, n)
            for k, r in enumerate(rects):
                if r[2] - r[0] < 9.0 or r[3] - r[1] < 9.0:
                    continue
                roll = R.random()
                if roll < 0.30:
                    placed.append(warehouse("Pier_{}_{}".format(bi, k), r, R, collection, detail))
                elif roll < 0.45:
                    placed.append(church("Church_{}_{}".format(bi, k), r, R, collection, detail))
                elif roll < 0.55:
                    placed.append(motel("Motel_{}_{}".format(bi, k), r, R, collection, detail))
                else:
                    placed.append(midrise("Water_{}_{}".format(bi, k), r, R, collection, detail))

    # a couple of civic anchors
    placed.append(subway_entrance("Subway_A", (-6.0, -6.0, 6.0, 6.0), R, collection))

    C.set_asset("buildings", [p for p in placed if p])
    print("  buildings placed: {}".format(len([p for p in placed if p])))
    return plan


if __name__ == "__main__":
    C.bootstrap(banner="M5 BUILDING TYPES")
    C.build_all_materials()
    build()
    C.report()