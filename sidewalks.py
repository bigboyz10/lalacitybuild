# =============================================================================
#  CITY BUILD  --  M3 : SIDEWALKS, CURBS, RAMPS, PAVEMENT FURNITURE
#  standalone:  blender -b -P sidewalks.py -- --quality preview
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
from core import CONFIG, plan_city, rng, add_box, add_plane

SW = 3.20          # sidewalk width
CURB_H = 0.15      # sidewalk slab height
CURB_TOP = 0.17    # curb stone top
Z_TOP = CURB_H


def _extra_materials():
    C.make_pbr("joint", base="#4b4844", roughness=0.92, bump=0.20,
               bump_scale=22, var_noise=9, grime=0.5)
    C.make_pbr("tactile", base="#a8863c", roughness=0.86, bump=0.40,
               bump_scale=30, var_noise=11, grime=0.45)
    C.make_pbr("grate", base="#3a3c3e", roughness=0.55, metallic=0.80,
               bump=0.30, bump_scale=20, var_noise=6, grime=0.4)
    C.make_pbr("soil_pit", base="#3b3128", roughness=0.97, bump=0.35,
               bump_scale=12, var_noise=9, grime=0.3)


def _add_box_bm(bm, cx, cy, cz, sx, sy, sz, rot=0.0):
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


def _add_ramp_bm(bm, back_x, back_y, rot, width=1.80, run=1.20, h=CURB_H):
    """Wedge descending from the sidewalk (back) to the road (front)."""
    ca, sa = math.cos(rot), math.sin(rot)

    def P(px, py, pz):
        return bm.verts.new((back_x + px * ca - py * sa,
                             back_y + px * sa + py * ca, pz))

    hw = width * 0.5
    b0 = P(-hw, 0.0, 0.0)
    b1 = P(hw, 0.0, 0.0)
    b2 = P(hw, run, 0.0)
    b3 = P(-hw, run, 0.0)
    t0 = P(-hw, 0.0, h)
    t1 = P(hw, 0.0, h)
    bm.faces.new((b0, b1, b2, b3))
    bm.faces.new((b0, b1, t1, t0))
    bm.faces.new((t0, t1, b2, b3))
    bm.faces.new((b0, t0, b3))
    bm.faces.new((b1, b2, t1))


def _quad_bm(bm, cx, cy, sx, sy, z, rot=0.0):
    ca, sa = math.cos(rot), math.sin(rot)
    hx, hy = sx * 0.5, sy * 0.5
    pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    vs = [bm.verts.new((cx + px * ca - py * sa,
                        cy + px * sa + py * ca, z)) for (px, py) in pts]
    bm.faces.new(vs)


# -----------------------------------------------------------------------------
def build():
    plan = plan_city()
    collection = C.col("CITY_Sidewalks")
    _extra_materials()
    R = rng("sidewalks")

    bm_slabs = bmesh.new()
    bm_curbs = bmesh.new()
    bm_ramps = bmesh.new()
    bm_tactile = bmesh.new()
    bm_joints = bmesh.new()

    tree_pits = []
    hatch_count = 0
    skylight_count = 0

    for bi, b in enumerate(plan["blocks"]):
        x0, x1, y0, y1 = b["x0"], b["x1"], b["y0"], b["y1"]
        cx, cy = b["cx"], b["cy"]
        w, h = b["w"], b["h"]
        if w < SW * 2 + 1.0 or h < SW * 2 + 1.0:
            continue

        # --- slabs (frame)
        _add_box_bm(bm_slabs, cx, y0 + SW * 0.5, CURB_H * 0.5, w, SW, CURB_H)
        _add_box_bm(bm_slabs, cx, y1 - SW * 0.5, CURB_H * 0.5, w, SW, CURB_H)
        _add_box_bm(bm_slabs, x0 + SW * 0.5, cy, CURB_H * 0.5, SW, h - SW * 2, CURB_H)
        _add_box_bm(bm_slabs, x1 - SW * 0.5, cy, CURB_H * 0.5, SW, h - SW * 2, CURB_H)

        # --- curb stones
        _add_box_bm(bm_curbs, cx, y0 + 0.11, CURB_TOP * 0.5, w, 0.22, CURB_TOP)
        _add_box_bm(bm_curbs, cx, y1 - 0.11, CURB_TOP * 0.5, w, 0.22, CURB_TOP)
        _add_box_bm(bm_curbs, x0 + 0.11, cy, CURB_TOP * 0.5, 0.22, h - 0.44, CURB_TOP)
        _add_box_bm(bm_curbs, x1 - 0.11, cy, CURB_TOP * 0.5, 0.22, h - 0.44, CURB_TOP)

        # --- corner ramps + tactile pads
        run = 1.20
        inset = 1.45
        corners = [
            (x0, y0, +1, +1, "S", "W"),
            (x1, y0, -1, +1, "S", "E"),
            (x0, y1, +1, -1, "N", "W"),
            (x1, y1, -1, -1, "N", "E"),
        ]
        for (ccx, ccy, sx, sy, d1, d2) in corners:
            # ramp toward d1 (south/north)
            if d1 == "S":
                bx, by, rot = ccx + sx * inset, ccy + run, math.pi
                tx, ty = bx, by + 0.55
                tq = (tx, ty, 1.70, 0.60, 0.0)
            else:
                bx, by, rot = ccx + sx * inset, ccy - run, 0.0
                tx, ty = bx, by - 0.55
                tq = (tx, ty, 1.70, 0.60, 0.0)
            _add_ramp_bm(bm_ramps, bx, by, rot)
            _quad_bm(bm_tactile, tq[0], tq[1], tq[2], tq[3], Z_TOP + 0.004, tq[4])

            # ramp toward d2 (west/east)
            if d2 == "W":
                bx, by, rot = ccx + run, ccy + sy * inset, math.pi * 0.5
                tx, ty = bx + 0.55, by
                tq = (tx, ty, 0.60, 1.70, 0.0)
            else:
                bx, by, rot = ccx - run, ccy + sy * inset, -math.pi * 0.5
                tx, ty = bx - 0.55, by
                tq = (tx, ty, 0.60, 1.70, 0.0)
            _add_ramp_bm(bm_ramps, bx, by, rot)
            _quad_bm(bm_tactile, tq[0], tq[1], tq[2], tq[3], Z_TOP + 0.004, tq[4])

        # --- expansion joints
        jx = x0 + SW + 1.6
        while jx < x1 - SW - 0.8:
            _quad_bm(bm_joints, jx, y0 + SW * 0.5, 0.035, SW - 0.1, Z_TOP + 0.002)
            _quad_bm(bm_joints, jx, y1 - SW * 0.5, 0.035, SW - 0.1, Z_TOP + 0.002)
            jx += 1.60
        jy = y0 + SW + 1.6
        while jy < y1 - SW - 0.8:
            _quad_bm(bm_joints, x0 + SW * 0.5, jy, SW - 0.1, 0.035, Z_TOP + 0.002)
            _quad_bm(bm_joints, x1 - SW * 0.5, jy, SW - 0.1, 0.035, Z_TOP + 0.002)
            jy += 1.60

        # --- tree pits along the long edges
        px = x0 + 5.0
        while px < x1 - 4.0:
            if R.random() < 0.55:
                py = y0 + 1.85
                tree_pits.append((px, py))
                _quad_bm(bm_joints, px, py, 1.30, 1.30, Z_TOP + 0.001)
                _add_box_bm(bm_slabs, px, py, Z_TOP + 0.012, 1.34, 0.10, 0.03)
                _add_box_bm(bm_slabs, px, py, Z_TOP + 0.012, 0.10, 1.34, 0.03)
            px += R.uniform(7.5, 11.0)
        px = x0 + 5.0
        while px < x1 - 4.0:
            if R.random() < 0.35:
                py = y1 - 1.85
                tree_pits.append((px, py))
                _quad_bm(bm_joints, px, py, 1.30, 1.30, Z_TOP + 0.001)
                _add_box_bm(bm_slabs, px, py, Z_TOP + 0.012, 1.34, 0.10, 0.03)
                _add_box_bm(bm_slabs, px, py, Z_TOP + 0.012, 0.10, 1.34, 0.03)
            px += R.uniform(8.5, 12.5)

        # --- cellar hatches / basement skylights
        if R.random() < 0.30:
            hx = R.uniform(x0 + 5.0, x1 - 5.0)
            hy = y0 + R.uniform(1.2, 2.4)
            add_box("CellarHatch_{:03d}".format(hatch_count), (1.15, 0.95, 0.06),
                    loc=(hx, hy, Z_TOP + 0.03), mat="metal_dark",
                    collection=collection, bevel=0.01)
            hatch_count += 1
        if R.random() < 0.22:
            sx_ = R.uniform(x0 + 5.0, x1 - 5.0)
            sy_ = y1 - R.uniform(1.2, 2.4)
            add_box("SkylightFrame_{:03d}".format(skylight_count), (1.55, 1.05, 0.10),
                    loc=(sx_, sy_, Z_TOP + 0.05), mat="metal_dark",
                    collection=collection, bevel=0.01)
            add_plane("SkylightGlass_{:03d}".format(skylight_count), (1.35, 0.85),
                      loc=(sx_, sy_, Z_TOP + 0.105), mat="glass_dirty",
                      collection=collection)
            skylight_count += 1

        # --- driveway aprons on residential blocks
        if b["district"] == "residential" and R.random() < 0.55:
            ax = R.uniform(x0 + 4.0, x1 - 4.0)
            add_plane("DrivewayApron_{:03d}".format(bi), (3.60, SW + 0.30),
                      loc=(ax, y0 + SW * 0.5, Z_TOP + 0.006),
                      mat="concrete", collection=collection)

    _mesh_from_bm("Sidewalk_Slabs", bm_slabs, "concrete", collection)
    _mesh_from_bm("Sidewalk_CurbStones", bm_curbs, "curb", collection)
    _mesh_from_bm("Sidewalk_CurbRamps", bm_ramps, "concrete", collection)
    _mesh_from_bm("Sidewalk_TactilePads", bm_tactile, "tactile", collection)
    _mesh_from_bm("Sidewalk_Joints", bm_joints, "joint", collection)

    C.set_asset("tree_pits", tree_pits)
    print("  sidewalk blocks: {}  tree pits: {}  hatches: {}  skylights: {}".format(
        len(plan["blocks"]), len(tree_pits), hatch_count, skylight_count))
    return plan


if __name__ == "__main__":
    C.bootstrap(banner="M3 SIDEWALKS")
    C.build_all_materials()
    build()
    C.report()