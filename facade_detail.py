# =============================================================================
#  CITY BUILD  --  M6 : FACADE DETAIL PASS
#  downspouts, conduit, laundry, blinds, interior clutter, wall lamps, vents
#  standalone:  blender -b -P facade_detail.py -- --quality preview
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
from core import CONFIG, U, rng, add_box, add_cylinder, add_plane
import buildings_core as BC
from buildings_core import STYLES, BASE_Z, FLOOR_H, GROUND_H

BLIND_Z = 0.0


def _extra_materials():
    C.make_pbr("blind", base="#b9ae98", roughness=0.92, bump=0.10,
               bump_scale=18, var_noise=7, grime=0.35)
    C.make_pbr("interior_dark", base="#1a1714", roughness=0.95, bump=0.10,
               bump_scale=10, var_noise=5, grime=0.2)


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
    ox, oy = nx * out, ny * out
    hw, hh = w * 0.5, h * 0.5
    p = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    vs = [bm.verts.new((cx + ux * a + ox, cy + uy * a + oy, cz + b)) for (a, b) in p]
    bm.faces.new(vs)


def _mesh(name, bm, mat, collection):
    if len(bm.faces) == 0:
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    C.link_object(ob, collection)
    if mat:
        ob.data.materials.append(C.M(mat))
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
def build():
    _extra_materials()
    collection = C.col("CITY_FacadeDetail")
    R = rng("facade_detail")
    buildings = [b for b in C.get_asset("buildings", []) if b]
    detail = 1.0 if CONFIG["quality"] == "high" else 0.6

    bm_down = bmesh.new()
    bm_conduit = bmesh.new()
    bm_blind = bmesh.new()
    bm_clutter = bmesh.new()
    bm_lamp_arm = bmesh.new()
    bm_vent = bmesh.new()
    bm_laundry = bmesh.new()
    bm_cloth = bmesh.new()

    n_down = n_blind = n_lamp = 0

    for b in buildings:
        rect = b["rect"]
        height = b["height"]
        style = b["style"]
        st = STYLES.get(style, STYLES["plaster"])
        floors = max(1, b.get("floors", 1))
        x0, y0, x1, y1 = rect
        if x1 - x0 < 4.0 or y1 - y0 < 4.0:
            continue

        # ---- downspouts at the four corners
        for (cx, cy) in ((x0 + 0.18, y0 + 0.18), (x1 - 0.18, y0 + 0.18),
                         (x0 + 0.18, y1 - 0.18), (x1 - 0.18, y1 - 0.18)):
            if R.random() < 0.75:
                _box_bm(bm_down, cx, cy, BASE_Z + height * 0.5,
                        0.13, 0.13, height, 0.0)
                n_down += 1
        # ---- vertical conduit on one facade
        if R.random() < 0.5:
            px, py, ux, uy, nx, ny, length = R.choice(_facades(rect))
            s = R.uniform(-length * 0.4, length * 0.4)
            _box_bm(bm_conduit, px + ux * s + nx * 0.09, py + uy * s + ny * 0.09,
                    BASE_Z + height * 0.5, 0.07, 0.07, height * 0.96,
                    math.atan2(uy, ux))

        # ---- window-aligned detail
        for (px, py, ux, uy, nx, ny, length) in _facades(rect):
            rot = math.atan2(uy, ux)
            cols = max(1, int(length // st["cols"]))
            step = length / cols
            usable = height - (GROUND_H if floors > 1 else 0.0)
            fl = max(1, int(usable // FLOOR_H))
            for f in range(fl):
                z = BASE_Z + (GROUND_H if floors > 1 else 0.0) + f * FLOOR_H + 1.45
                if z + st["win_h"] * 0.5 > BASE_Z + height - 0.4:
                    continue
                for c in range(cols):
                    s = -length * 0.5 + step * (c + 0.5)
                    cx = px + ux * s
                    cy = py + uy * s
                    # blinds
                    if R.random() < 0.28 * detail:
                        _vquad_bm(bm_blind, cx, cy, z, ux, uy, nx, ny,
                                  st["win_w"] * 0.92, st["win_h"] * 0.92, out=0.005)
                        n_blind += 1
                    # interior clutter behind ground floor glazing
                    if f == 0 and R.random() < 0.35:
                        _box_bm(bm_clutter,
                                cx - nx * 0.55, cy - ny * 0.55, z - 0.35,
                                st["win_w"] * 0.8, 0.9, 0.9, rot)
            # ---- laundry lines on residential facades
            if st["balcony"] > 0.3 and length > 7.0 and R.random() < 0.35:
                f = R.randint(1, max(1, fl - 1))
                z = BASE_Z + GROUND_H + f * FLOOR_H + 2.35
                s = R.uniform(-length * 0.25, length * 0.25)
                ax = px + ux * s + nx * 0.55
                ay = py + uy * s + ny * 0.55
                _box_bm(bm_laundry, ax, ay, z, 2.6, 0.02, 0.02, rot)
                for k in range(3):
                    t = -0.9 + k * 0.9
                    _vquad_bm(bm_cloth,
                              ax + ux * t, ay + uy * t, z - 0.42,
                              ux, uy, nx, ny, 0.55, 0.80, out=0.0)
            # ---- wall vents
            if R.random() < 0.3:
                s = R.uniform(-length * 0.4, length * 0.4)
                _box_bm(bm_vent, px + ux * s + nx * 0.10,
                        py + uy * s + ny * 0.10,
                        BASE_Z + R.uniform(3.0, max(3.2, height - 1.0)),
                        0.42, 0.12, 0.32, rot)

        # ---- entrance wall lamps
        if R.random() < 0.55:
            px, py, ux, uy, nx, ny, length = _facades(rect)[0]
            for sgn in (-1, 1):
                s = sgn * 1.1
                bx = px + ux * s + nx * 0.22
                by = py + uy * s + ny * 0.22
                _box_bm(bm_lamp_arm, bx, by, BASE_Z + 2.75, 0.10, 0.10, 0.10, 0.0)
                n_lamp += 1
                add_box("WallLamp_{}_{}".format(b["name"], sgn),
                        (0.16, 0.16, 0.22),
                        loc=(bx + nx * 0.10, by + ny * 0.10, BASE_Z + 2.62),
                        mat="lamp_warm", collection=collection)

    _mesh("Facade_Downspouts", bm_down, "metal_galv", collection)
    _mesh("Facade_Conduit", bm_conduit, "metal_galv", collection)
    _mesh("Facade_Blinds", bm_blind, "blind", collection)
    _mesh("Facade_InteriorClutter", bm_clutter, "interior_dark", collection)
    _mesh("Facade_LampArms", bm_lamp_arm, "metal_dark", collection)
    _mesh("Facade_Vents", bm_vent, "metal_galv", collection)
    _mesh("Facade_LaundryLines", bm_laundry, "metal_dark", collection)
    _mesh("Facade_Laundry", bm_cloth, "fabric_red", collection)

    print("  downspouts: {}  blinds: {}  lamps: {}".format(n_down, n_blind, n_lamp))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="M6 FACADE DETAIL")
    C.build_all_materials()
    import buildings_types
    buildings_types.build()
    build()
    C.report()