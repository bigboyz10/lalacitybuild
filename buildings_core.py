# =============================================================================
#  CITY BUILD  --  M4 : BUILDING CORE  (massing, facades, windows, shopfronts)
#  standalone:  blender -b -P buildings_core.py -- --quality preview
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
from core import CONFIG, U, rng, add_box, add_plane

BASE_Z = 0.15
FLOOR_H = U["floor_h"]
GROUND_H = 4.20


# -----------------------------------------------------------------------------
# style table
# -----------------------------------------------------------------------------
STYLES = {
    "curtain": dict(wall="glass_dark", frame="metal_dark", sill="metal_dark",
                    win_w=1.90, win_h=2.30, cols=2.60, balcony=0.0, fire=0.0,
                    cornice=0.0, shop=0.85, plinth="concrete_panel", roof="flat"),
    "stone_old": dict(wall="stone", frame="stone_dark", sill="stone",
                      win_w=1.15, win_h=2.05, cols=2.70, balcony=0.10, fire=0.35,
                      cornice=1.0, shop=0.55, plinth="stone_dark", roof="flat"),
    "brick_old": dict(wall="brick", frame="stone", sill="stone",
                      win_w=1.10, win_h=1.95, cols=2.55, balcony=0.10, fire=0.50,
                      cornice=1.0, shop=0.60, plinth="stone_dark", roof="flat"),
    "brick_modern": dict(wall="brick_pale", frame="metal_dark", sill="concrete",
                         win_w=1.30, win_h=1.80, cols=2.45, balcony=0.35, fire=0.0,
                         cornice=0.4, shop=0.50, plinth="concrete", roof="flat"),
    "plaster": dict(wall="plaster", frame="stone", sill="stone",
                    win_w=1.05, win_h=1.85, cols=2.60, balcony=0.45, fire=0.15,
                    cornice=1.0, shop=0.45, plinth="stone_dark", roof="flat"),
    "plaster_pink": dict(wall="plaster_pink", frame="stone", sill="stone",
                         win_w=1.05, win_h=1.85, cols=2.60, balcony=0.40, fire=0.10,
                         cornice=1.0, shop=0.40, plinth="stone_dark", roof="flat"),
    "plaster_teal": dict(wall="plaster_teal", frame="stone", sill="stone",
                         win_w=1.05, win_h=1.85, cols=2.60, balcony=0.40, fire=0.10,
                         cornice=1.0, shop=0.40, plinth="stone_dark", roof="flat"),
    "concrete_panel": dict(wall="concrete_panel", frame="metal_dark", sill="concrete",
                           win_w=1.35, win_h=1.75, cols=2.50, balcony=0.55, fire=0.0,
                           cornice=0.3, shop=0.35, plinth="concrete", roof="flat"),
    "industrial": dict(wall="brick_dark", frame="metal_dark", sill="concrete",
                       win_w=2.20, win_h=1.30, cols=3.60, balcony=0.0, fire=0.25,
                       cornice=0.2, shop=0.0, plinth="concrete", roof="flat"),
    "warehouse": dict(wall="metal_galv", frame="metal_dark", sill="metal",
                      win_w=2.40, win_h=1.10, cols=4.20, balcony=0.0, fire=0.0,
                      cornice=0.0, shop=0.0, plinth="concrete", roof="flat"),
}


def pick_style(district, R):
    if district == "downtown":
        return R.choice(["curtain", "curtain", "stone_old", "concrete_panel"])
    if district == "midtown":
        return R.choice(["brick_old", "brick_modern", "plaster", "stone_old",
                         "concrete_panel", "plaster_pink"])
    if district == "residential":
        return R.choice(["brick_old", "plaster", "plaster_pink", "plaster_teal",
                         "brick_modern", "brick_old"])
    if district == "industrial":
        return R.choice(["industrial", "industrial", "warehouse"])
    if district == "waterfront":
        return R.choice(["brick_old", "stone_old", "warehouse", "brick_modern"])
    if district == "parkland":
        return R.choice(["plaster", "brick_modern"])
    return "plaster"


# -----------------------------------------------------------------------------
# bmesh primitives
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


def _vquad_bm(bm, cx, cy, cz, ux, uy, nx, ny, w, h, out=0.0):
    """Vertical quad on a facade, facing along (nx, ny)."""
    ox, oy = nx * out, ny * out
    hw, hh = w * 0.5, h * 0.5
    p = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    vs = []
    for (a, b) in p:
        vs.append(bm.verts.new((cx + ux * a + ox, cy + uy * a + oy, cz + b)))
    bm.faces.new(vs)


def _mesh(name, bm, mat, collection, smooth=False):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    C.link_object(ob, collection)
    if mat:
        ob.data.materials.append(C.M(mat))
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def _facades(rect):
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    w, h = x1 - x0, y1 - y0
    return [
        (cx, y0, 1.0, 0.0, 0.0, -1.0, w),
        (cx, y1, 1.0, 0.0, 0.0, 1.0, w),
        (x0, cy, 0.0, 1.0, -1.0, 0.0, h),
        (x1, cy, 0.0, 1.0, 1.0, 0.0, h),
    ]


# -----------------------------------------------------------------------------
# window / shopfront emitters
# -----------------------------------------------------------------------------
def emit_window(bm_frame, bm_glass, bm_sill, bm_balcony, bm_rail,
                px, py, ux, uy, nx, ny, s, z, ww, wh, style, R,
                balcony=False, depth=0.10, bm_reveal=None, bm_room=None,
                recess=0.22, interior=True, mullion=True):
    """One window.

    Glass is set back into a reveal rather than sitting flush, and a dark room
    volume is built behind it.  That gives real parallax at eye level: the
    opening reads as a hole into a space instead of a decal on a wall, which
    was the single biggest tell in the previous build.
    """
    rot = math.atan2(uy, ux)
    cx = px + ux * s
    cy = py + uy * s

    # frame slab (reads as a chunky surround)
    _box_bm(bm_frame, cx + nx * 0.02, cy + ny * 0.02, z,
            ww + 0.16, depth, wh + 0.16, rot)

    # --- reveal: jambs, head and cill faces lining the recess -------------
    target = bm_reveal if bm_reveal is not None else bm_frame
    inner = -recess * 0.5
    for sgn in (-1, 1):
        _box_bm(target,
                cx + ux * (sgn * (ww * 0.5 + 0.03)) + nx * inner,
                cy + uy * (sgn * (ww * 0.5 + 0.03)) + ny * inner,
                z, 0.07, recess, wh, rot)
    _box_bm(target, cx + nx * inner, cy + ny * inner, z + wh * 0.5 + 0.03,
            ww + 0.14, recess, 0.07, rot)
    _box_bm(target, cx + nx * inner, cy + ny * inner, z - wh * 0.5 - 0.03,
            ww + 0.14, recess, 0.07, rot)

    # --- room volume behind the opening -----------------------------------
    if interior and bm_room is not None:
        d = R.uniform(1.6, 3.0)
        _box_bm(bm_room, cx - nx * (d * 0.5 + recess), cy - ny * (d * 0.5 + recess),
                z - wh * 0.10, ww + 0.9, d, wh + 1.5, rot)
        # a slab of furniture / clutter catching the light near the glass
        if R.random() < 0.55:
            fh = R.uniform(0.5, 1.1)
            _box_bm(bm_room,
                    cx - nx * (recess + R.uniform(0.45, 1.0)),
                    cy - ny * (recess + R.uniform(0.45, 1.0)),
                    z - wh * 0.5 + fh * 0.5,
                    ww * R.uniform(0.35, 0.85), R.uniform(0.3, 0.7), fh,
                    rot + R.uniform(-0.3, 0.3))

    # glass, set back inside the reveal
    _vquad_bm(bm_glass, cx - nx * recess, cy - ny * recess, z,
              ux, uy, nx, ny, ww, wh, out=0.0)

    # --- mullion / transom so large panes are not single sheets -----------
    if mullion and ww > 1.25:
        _box_bm(bm_frame, cx - nx * (recess - 0.02), cy - ny * (recess - 0.02),
                z, 0.06, 0.06, wh, rot)
    if mullion and wh > 1.9:
        _box_bm(bm_frame, cx - nx * (recess - 0.02), cy - ny * (recess - 0.02),
                z + wh * 0.18, ww, 0.06, 0.06, rot)
    # sill
    _box_bm(bm_sill, cx + nx * 0.09, cy + ny * 0.09, z - wh * 0.5 - 0.07,
            ww + 0.30, 0.20, 0.09, rot)

    if balcony and R.random() < 0.55:
        bw = ww + 0.55
        bd = 1.05
        _box_bm(bm_balcony, cx + nx * (bd * 0.5), cy + ny * (bd * 0.5),
                z - wh * 0.5 - 0.10, bw, bd, 0.13, rot)
        # railing: front + two sides + top rail
        fx = cx + nx * bd
        fy = cy + ny * bd
        _box_bm(bm_rail, fx, fy, z - wh * 0.5 + 0.42, bw, 0.06, 0.06, rot)
        _box_bm(bm_rail, fx, fy, z - wh * 0.5 + 0.05, bw, 0.05, 0.05, rot)
        for sgn in (-1, 1):
            sx_ = cx + ux * (sgn * bw * 0.5) + nx * (bd * 0.5)
            sy_ = cy + uy * (sgn * bw * 0.5) + ny * (bd * 0.5)
            _box_bm(bm_rail, sx_, sy_, z - wh * 0.5 + 0.24, 0.05, bd, 0.05, rot)
        for k in range(4):
            t = -bw * 0.5 + bw * (k + 0.5) / 4.0
            _box_bm(bm_rail, cx + ux * t + nx * bd, cy + uy * t + ny * bd,
                    z - wh * 0.5 + 0.24, 0.035, 0.035, 0.42, rot)


def emit_shopfront(bm_frame, bm_glass, bm_bulk, bm_awning, bm_sign,
                   px, py, ux, uy, nx, ny, length, z0, R, style):
    rot = math.atan2(uy, ux)
    # bulkhead
    _box_bm(bm_bulk, px + nx * 0.10, py + ny * 0.10, z0 + 0.35,
            length - 0.4, 0.24, 0.70, rot)
    # glazing bays
    bays = max(1, int((length - 0.8) / 2.4))
    bw = (length - 0.8) / bays
    for i in range(bays):
        s = -length * 0.5 + 0.4 + bw * (i + 0.5)
        cx = px + ux * s
        cy = py + uy * s
        _box_bm(bm_frame, cx + nx * 0.02, cy + ny * 0.02, z0 + 1.55,
                bw - 0.10, 0.12, 2.30, rot)
        _vquad_bm(bm_glass, cx, cy, z0 + 1.55, ux, uy, nx, ny,
                  bw - 0.22, 2.10, out=0.08)
    # awning
    if R.random() < 0.6:
        aw = length * 0.92
        _box_bm(bm_awning, px + nx * 0.85, py + ny * 0.85, z0 + 3.05,
                aw, 1.70, 0.10, rot)
        _box_bm(bm_awning, px + nx * 1.68, py + ny * 1.68, z0 + 2.80,
                aw, 0.08, 0.55, rot)
    # sign band
    _box_bm(bm_sign, px + nx * 0.14, py + ny * 0.14, z0 + 3.55,
            length - 0.3, 0.16, 0.85, rot)


def emit_fire_escape(bm, px, py, ux, uy, nx, ny, length, z0, floors, R):
    rot = math.atan2(uy, ux)
    fx = px + nx * 1.15
    fy = py + ny * 1.15
    for f in range(floors):
        z = z0 + GROUND_H + f * FLOOR_H + 0.10
        _box_bm(bm, fx, fy, z, 2.60, 1.10, 0.07, rot)
        # railings
        _box_bm(bm, fx + nx * 0.52, fy + ny * 0.52, z + 0.55, 2.60, 0.05, 0.05, rot)
        _box_bm(bm, fx + nx * 0.52, fy + ny * 0.52, z + 0.20, 2.60, 0.04, 0.04, rot)
        for sgn in (-1, 1):
            _box_bm(bm, fx + ux * (sgn * 1.28), fy + uy * (sgn * 1.28),
                    z + 0.35, 0.05, 1.05, 0.05, rot)
        # stair flight to the next level
        if f < floors - 1:
            for k in range(7):
                t = k / 7.0
                _box_bm(bm,
                        fx + ux * (-1.0 + 2.0 * t) + nx * 0.0,
                        fy + uy * (-1.0 + 2.0 * t) + ny * 0.0,
                        z + 0.10 + t * (FLOOR_H - 0.20),
                        0.34, 0.30, 0.05, rot)


def emit_ac_units(bm, px, py, ux, uy, nx, ny, length, z0, height, R, count):
    rot = math.atan2(uy, ux)
    for i in range(count):
        s = R.uniform(-length * 0.42, length * 0.42)
        z = z0 + R.uniform(GROUND_H + 1.0, max(GROUND_H + 1.2, height - 1.2))
        cx = px + ux * s + nx * 0.30
        cy = py + uy * s + ny * 0.30
        _box_bm(bm, cx, cy, z, 0.62, 0.42, 0.52, rot)
        _box_bm(bm, cx + nx * 0.24, cy + ny * 0.24, z, 0.50, 0.06, 0.40, rot)


# -----------------------------------------------------------------------------
# main building emitter
# -----------------------------------------------------------------------------
def emit_building(name, rect, height, style, collection, R, base_z=BASE_Z,
                  detail=1.0, ground_floor=True):
    x0, y0, x1, y1 = rect
    w = x1 - x0
    h = y1 - y0
    if w < 3.0 or h < 3.0:
        return None
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    st = STYLES[style]

    bm_wall = bmesh.new()
    bm_frame = bmesh.new()
    bm_glass = bmesh.new()
    bm_sill = bmesh.new()
    bm_balcony = bmesh.new()
    bm_rail = bmesh.new()
    bm_plinth = bmesh.new()
    bm_cornice = bmesh.new()
    bm_shop_bulk = bmesh.new()
    bm_awning = bmesh.new()
    bm_sign = bmesh.new()
    bm_ac = bmesh.new()
    bm_fire = bmesh.new()

    # main mass
    _box_bm(bm_wall, cx, cy, base_z + height * 0.5, w, h, height)

    # plinth
    _box_bm(bm_plinth, cx, cy, base_z + 0.35, w + 0.16, h + 0.16, 0.70)

    # cornice + parapet
    if st["cornice"] > 0.5:
        _box_bm(bm_cornice, cx, cy, base_z + height + 0.16,
                w + 0.42, h + 0.42, 0.34)
        _box_bm(bm_cornice, cx, cy, base_z + height + 0.34,
                w + 0.24, h + 0.24, 0.16)
    _box_bm(bm_cornice, cx, cy, base_z + height + 0.05,
            w + 0.10, h + 0.10, 0.12)

    # floors / columns
    usable = height - (GROUND_H if ground_floor else 0.0)
    floors = max(1, int(usable // FLOOR_H))
    if floors < 1:
        floors = 1

    glass_mat = R.choice(["glass", "glass", "glass_dark", "glass_dirty"])

    for (px, py, ux, uy, nx, ny, length) in _facades(rect):
        rot = math.atan2(uy, ux)
        cols = max(1, int(length // st["cols"]))
        win_w = st["win_w"]
        win_h = st["win_h"]
        step = length / cols

        # ---- upper floors
        for f in range(floors):
            z = base_z + (GROUND_H if ground_floor else 0.0) + f * FLOOR_H + 1.45
            if z + win_h * 0.5 > base_z + height - 0.4:
                continue
            for c in range(cols):
                if detail < 1.0 and R.random() > detail:
                    continue
                s = -length * 0.5 + step * (c + 0.5)
                emit_window(bm_frame, bm_glass, bm_sill, bm_balcony, bm_rail,
                            px, py, ux, uy, nx, ny, s, z, win_w, win_h,
                            style, R,
                            balcony=(st["balcony"] > 0.3 and R.random() < st["balcony"]))
        # ---- ground floor
        if ground_floor:
            if st["shop"] > 0.3 and R.random() < st["shop"]:
                emit_shopfront(bm_frame, bm_glass, bm_shop_bulk, bm_awning,
                               bm_sign, px, py, ux, uy, nx, ny,
                               length - 0.5, base_z, R, style)
            else:
                # residential entry: door + two windows
                s = 0.0
                _box_bm(bm_frame, px + nx * 0.03, py + ny * 0.03, base_z + 1.05,
                        1.25, 0.14, 2.30, rot)
                _vquad_bm(bm_glass, px, py, base_z + 1.05, ux, uy, nx, ny,
                          1.05, 2.10, out=0.09)
                for sgn in (-1, 1):
                    s2 = sgn * min(length * 0.28, 3.2)
                    _box_bm(bm_frame, px + ux * s2 + nx * 0.02,
                            py + uy * s2 + ny * 0.02, base_z + 1.55,
                            win_w + 0.16, 0.12, win_h + 0.16, rot)
                    _vquad_bm(bm_glass, px + ux * s2, py + uy * s2, base_z + 1.55,
                              ux, uy, nx, ny, win_w, win_h, out=0.08)
        # ---- fire escape on one street facade
        if st["fire"] > 0.0 and R.random() < st["fire"] and length > 6.0:
            emit_fire_escape(bm_fire, px, py, ux, uy, nx, ny, length,
                             base_z, floors, R)
            break
        # ---- AC units
        if R.random() < 0.5 and length > 5.0:
            emit_ac_units(bm_ac, px, py, ux, uy, nx, ny, length, base_z,
                          height, R, R.randint(1, 3))

    objs = []
    objs.append(_mesh(name + "_Mass", bm_wall, st["wall"], collection))
    if len(bm_plinth.faces):
        objs.append(_mesh(name + "_Plinth", bm_plinth, st["plinth"], collection))
    if len(bm_cornice.faces):
        objs.append(_mesh(name + "_Cornice", bm_cornice, st["sill"], collection))
    if len(bm_frame.faces):
        objs.append(_mesh(name + "_Frames", bm_frame, st["frame"], collection))
    if len(bm_glass.faces):
        objs.append(_mesh(name + "_Glass", bm_glass, glass_mat, collection))
    if len(bm_sill.faces):
        objs.append(_mesh(name + "_Sills", bm_sill, st["sill"], collection))
    if len(bm_balcony.faces):
        objs.append(_mesh(name + "_Balconies", bm_balcony, "concrete", collection))
    if len(bm_rail.faces):
        objs.append(_mesh(name + "_Railings", bm_rail, "metal_dark", collection))
    if len(bm_shop_bulk.faces):
        objs.append(_mesh(name + "_ShopBulk", bm_shop_bulk, st["frame"], collection))
    if len(bm_awning.faces):
        objs.append(_mesh(name + "_Awnings", bm_awning,
                          R.choice(["fabric_red", "fabric_green"]), collection))
    if len(bm_sign.faces):
        objs.append(_mesh(name + "_SignBand", bm_sign, "metal_dark", collection))
    if len(bm_ac.faces):
        objs.append(_mesh(name + "_ACUnits", bm_ac, "metal_galv", collection))
    if len(bm_fire.faces):
        objs.append(_mesh(name + "_FireEscape", bm_fire, "metal_dark", collection))

    return {"name": name, "rect": rect, "height": height, "style": style,
            "objects": objs, "floors": floors}


# -----------------------------------------------------------------------------
# standalone demo: one building of each style on a row
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    C.bootstrap(banner="M4 BUILDING CORE")
    C.build_all_materials()
    collection = C.col("CITY_Buildings")
    R = rng("demo_core")
    x = -60.0
    for i, style in enumerate(sorted(STYLES)):
        rect = (x, -8.0, x + 18.0, 8.0)
        emit_building("Demo_{}".format(style), rect,
                      12.0 + i * 3.0, style, collection, R)
        x += 22.0
    C.report()