# =============================================================================
#  CITY BUILD  --  M8 : DAMAGE, DECAY & ABANDONMENT
#  boarded windows, water staining, soot, cracks, peeling paint, rubble
#  standalone:  blender -b -P damage.py -- --quality preview
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
from core import CONFIG, U, rng, add_box, add_rock
from buildings_core import BASE_Z, FLOOR_H, GROUND_H, STYLES


def _extra_materials():
    C.make_pbr("soot", base="#1c1a18", roughness=0.97, bump=0.15,
               bump_scale=14, var_noise=8, grime=0.2)
    C.make_pbr("stain", base="#4b4238", roughness=0.94, bump=0.12,
               bump_scale=16, var_noise=9, grime=0.3)
    C.make_pbr("plywood", base="#8a6a45", roughness=0.95, bump=0.30,
               bump_scale=22, var_noise=10, grime=0.4)
    C.make_pbr("spall", base="#b0a89c", roughness=0.93, bump=0.35,
               bump_scale=18, var_noise=9, grime=0.4)


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


def build():
    _extra_materials()
    collection = C.col("CITY_Damage")
    R = rng("damage")
    buildings = [b for b in C.get_asset("buildings", []) if b]
    detail = 1.0 if CONFIG["quality"] == "high" else 0.6

    bm_board = bmesh.new()
    bm_stain = bmesh.new()
    bm_soot = bmesh.new()
    bm_crack = bmesh.new()
    bm_spall = bmesh.new()

    n_board = n_stain = n_soot = n_crack = 0

    for b in buildings:
        rect = b["rect"]
        height = b["height"]
        style = b["style"]
        st = STYLES.get(style, STYLES["plaster"])
        x0, y0, x1, y1 = rect
        if x1 - x0 < 4.5 or y1 - y0 < 4.5:
            continue
        floors = max(1, b.get("floors", 1))
        abandoned = R.random() < 0.14

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

                    # boarded windows on abandoned buildings
                    if abandoned and f < 3 and R.random() < 0.55 * detail:
                        _vquad_bm(bm_board, cx, cy, z, ux, uy, nx, ny,
                                  st["win_w"] + 0.10, st["win_h"] * 0.30,
                                  out=0.075)
                        _vquad_bm(bm_board, cx, cy, z + st["win_h"] * 0.28,
                                  ux, uy, nx, ny, st["win_w"] + 0.10,
                                  st["win_h"] * 0.26, out=0.075)
                        _vquad_bm(bm_board, cx, cy, z - st["win_h"] * 0.28,
                                  ux, uy, nx, ny, st["win_w"] + 0.10,
                                  st["win_h"] * 0.26, out=0.075)
                        n_board += 1

                    # water staining running down from the sill
                    if R.random() < 0.30 * detail:
                        sw = st["win_w"] * R.uniform(0.25, 0.6)
                        sh = R.uniform(0.8, 2.6)
                        _vquad_bm(bm_stain,
                                  cx + ux * R.uniform(-0.3, 0.3), cy,
                                  z - st["win_h"] * 0.5 - sh * 0.5,
                                  ux, uy, nx, ny, sw, sh, out=0.006)
                        n_stain += 1

            # soot / fire scarring near the roofline
            if R.random() < 0.10:
                sw = length * R.uniform(0.3, 0.8)
                sh = R.uniform(2.0, 5.0)
                _vquad_bm(bm_soot, px, py, BASE_Z + height - sh * 0.5,
                          ux, uy, nx, ny, sw, sh, out=0.008)
                n_soot += 1

            # spalled / peeling plaster patches
            if R.random() < 0.35 * detail:
                for k in range(R.randint(1, 3)):
                    s = R.uniform(-length * 0.42, length * 0.42)
                    zc = BASE_Z + R.uniform(2.0, max(2.2, height - 1.5))
                    _vquad_bm(bm_spall, px + ux * s, py + uy * s, zc,
                              ux, uy, nx, ny, R.uniform(0.6, 1.8),
                              R.uniform(0.5, 1.4), out=0.005)

            # structural cracks
            if R.random() < 0.30 * detail:
                s0 = R.uniform(-length * 0.4, length * 0.4)
                z0 = BASE_Z + R.uniform(1.5, max(1.6, height * 0.5))
                pts = []
                cx_s = s0
                cz_s = z0
                ang = R.uniform(-0.4, 0.4) + (math.pi * 0.5 if R.random() < 0.5 else 0.0)
                for k in range(R.randint(4, 8)):
                    pts.append((cx_s, cz_s))
                    ang += R.uniform(-0.5, 0.5)
                    cx_s += math.cos(ang) * R.uniform(0.3, 0.9)
                    cz_s += math.sin(ang) * R.uniform(0.3, 0.9)
                for k in range(len(pts) - 1):
                    ax, az = pts[k]
                    bx, bz = pts[k + 1]
                    mx = (ax + bx) * 0.5
                    mz = (az + bz) * 0.5
                    ln = math.hypot(bx - ax, bz - az) or 0.01
                    ang2 = math.atan2(bz - az, bx - ax)
                    _vquad_bm(bm_crack,
                              px + ux * mx, py + uy * mx, BASE_Z + mz,
                              ux, uy, nx, ny, ln, 0.035, out=0.007)
                    n_crack += 1

        # rubble at the base of derelict buildings
        if abandoned:
            for i in range(R.randint(4, 10)):
                rx = R.uniform(x0 - 1.0, x1 + 1.0)
                ry = R.uniform(y0 - 1.0, y1 + 1.0)
                s = R.uniform(0.15, 0.55)
                add_rock("{}_Rubble{}".format(b["name"], i), (s * 1.4, s, s * 0.7),
                         loc=(rx, ry, BASE_Z + s * 0.2),
                         rot=(0, 0, R.uniform(0, math.tau)),
                         mat="concrete", collection=collection, seed=hash(b["name"]) % 9999 + i)

    _mesh("Damage_BoardedWindows", bm_board, "plywood", collection)
    _mesh("Damage_WaterStains", bm_stain, "stain", collection)
    _mesh("Damage_Soot", bm_soot, "soot", collection)
    _mesh("Damage_Cracks", bm_crack, "soot", collection)
    _mesh("Damage_Spall", bm_spall, "spall", collection)

    print("  boarded: {}  stains: {}  soot: {}  crack segs: {}".format(
        n_board, n_stain, n_soot, n_crack))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="M8 DAMAGE")
    C.build_all_materials()
    import buildings_types
    buildings_types.build()
    build()
    C.report()