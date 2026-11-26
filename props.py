# =============================================================================
#  CITY BUILD  --  M9 : STREET FURNITURE & PROPS
#  standalone:  blender -b -P props.py -- --quality preview
# =============================================================================
import bpy
import bmesh
import math
import os
import sys
from mathutils import Matrix, Vector

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, U, rng, plan_city

BASE_Z = 0.15


# -----------------------------------------------------------------------------
class Part:
    """Accumulates primitives into one bmesh, built at the origin."""

    def __init__(self):
        self.bm = bmesh.new()

    def box(self, cx=0.0, cy=0.0, cz=0.0, sx=1.0, sy=1.0, sz=1.0, rot=0.0):
        ca, sa = math.cos(rot), math.sin(rot)
        hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
        corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        bot, top = [], []
        for (px, py) in corners:
            wx = cx + px * ca - py * sa
            wy = cy + px * sa + py * ca
            bot.append(self.bm.verts.new((wx, wy, cz - hz)))
            top.append(self.bm.verts.new((wx, wy, cz + hz)))
        self.bm.faces.new(list(reversed(bot)))
        self.bm.faces.new(top)
        for i in range(4):
            j = (i + 1) % 4
            self.bm.faces.new((bot[i], bot[j], top[j], top[i]))

    def cyl(self, cx=0.0, cy=0.0, cz=0.0, r=0.5, depth=1.0, seg=12,
            rot=(0.0, 0.0, 0.0), rtop=None):
        rt = r if rtop is None else rtop
        m = (Matrix.Rotation(rot[2], 4, 'Z') @
             Matrix.Rotation(rot[1], 4, 'Y') @
             Matrix.Rotation(rot[0], 4, 'X'))
        off = Vector((cx, cy, cz))
        bot, top = [], []
        for i in range(seg):
            a = 2.0 * math.pi * i / seg
            bot.append(self.bm.verts.new(m @ Vector((r * math.cos(a), r * math.sin(a), -depth * 0.5)) + off))
            top.append(self.bm.verts.new(m @ Vector((rt * math.cos(a), rt * math.sin(a), depth * 0.5)) + off))
        for i in range(seg):
            j = (i + 1) % seg
            self.bm.faces.new((bot[i], bot[j], top[j], top[i]))
        if r > 1e-6:
            self.bm.faces.new(list(reversed(bot)))
        self.bm.faces.new(top)

    def sphere(self, cx=0.0, cy=0.0, cz=0.0, r=0.5, subdiv=2, scale=(1, 1, 1)):
        bm2 = bmesh.new()
        try:
            bmesh.ops.create_icosphere(bm2, subdivisions=subdiv, radius=1.0)
        except TypeError:
            bmesh.ops.create_icosphere(bm2, subdivisions=subdiv, diameter=1.0)
        for v in bm2.verts:
            v.co.x = v.co.x * r * scale[0] + cx
            v.co.y = v.co.y * r * scale[1] + cy
            v.co.z = v.co.z * r * scale[2] + cz
        me = bpy.data.meshes.new("_tmp")
        bm2.to_mesh(me)
        bm2.free()
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)

    def obj(self, name, mat, collection, loc=(0, 0, 0), rot=0.0, bevel=0.0):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name + "_mesh")
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(name, me)
        ob.location = loc
        ob.rotation_euler = (0.0, 0.0, rot)
        C.link_object(ob, collection)
        if mat:
            ob.data.materials.append(C.M(mat))
        if bevel > 0.0:
            md = ob.modifiers.new("Bevel", "BEVEL")
            md.width = bevel
            md.segments = 2
            md.limit_method = 'ANGLE'
        return ob


# -----------------------------------------------------------------------------
# prop builders -> list of (Part, material)
# -----------------------------------------------------------------------------
def p_trash_can():
    p = Part()
    p.cyl(0, 0, 0.45, 0.27, 0.88, 14)
    p.cyl(0, 0, 0.90, 0.29, 0.05, 14)
    p.cyl(0, 0, 0.93, 0.20, 0.03, 12)
    return [(p, "metal_galv")]


def p_recycling_bin():
    p = Part()
    p.box(0, 0, 0.50, 0.56, 0.50, 1.00)
    p.box(0, 0, 1.02, 0.60, 0.54, 0.06)
    return [(p, "plastic")]


def p_dumpster():
    p = Part()
    p.box(0, 0, 0.62, 2.10, 1.25, 1.20)
    p.box(0, 0, 1.26, 2.16, 1.31, 0.10)
    p.box(0, -0.66, 0.62, 1.90, 0.06, 0.90)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(sx * 0.85, sy * 0.48, 0.10, 0.10, 0.16, 8,
                  rot=(0, math.pi * 0.5, 0))
    return [(p, "metal_dark")]


def p_bench():
    p = Part()
    for i in range(4):
        p.box(0, -0.24 + i * 0.16, 0.45, 1.80, 0.13, 0.05)
    for i in range(3):
        p.box(0, 0.30, 0.62 + i * 0.16, 1.80, 0.05, 0.13)
    for sx in (-1, 1):
        p.box(sx * 0.75, 0.0, 0.22, 0.07, 0.55, 0.44)
        p.box(sx * 0.75, 0.30, 0.55, 0.07, 0.07, 0.60)
    return [(p, "wood_pale")]


def p_picnic_table():
    p = Part()
    p.box(0, 0, 0.74, 1.90, 0.90, 0.06)
    for sy in (-1, 1):
        p.box(0, sy * 0.78, 0.45, 1.90, 0.28, 0.05)
    for sx in (-1, 1):
        p.box(sx * 0.70, 0, 0.37, 0.08, 1.60, 0.72)
    return [(p, "wood_pale")]


def p_bollard():
    p = Part()
    p.cyl(0, 0, 0.45, 0.09, 0.90, 10)
    p.cyl(0, 0, 0.91, 0.11, 0.05, 10)
    return [(p, "metal_dark")]


def p_hydrant():
    p = Part()
    p.cyl(0, 0, 0.32, 0.14, 0.62, 12)
    p.cyl(0, 0, 0.66, 0.17, 0.10, 12)
    p.cyl(0, 0, 0.74, 0.10, 0.10, 10, rtop=0.03)
    p.cyl(0.16, 0, 0.42, 0.07, 0.16, 8, rot=(0, math.pi * 0.5, 0))
    p.cyl(-0.16, 0, 0.42, 0.07, 0.16, 8, rot=(0, math.pi * 0.5, 0))
    return [(p, "paint_red")]


def p_mailbox():
    p = Part()
    p.box(0, 0, 0.55, 0.55, 0.45, 0.70)
    p.cyl(0, 0, 0.90, 0.28, 0.50, 12, rot=(0, math.pi * 0.5, 0))
    p.box(0, 0, 0.20, 0.10, 0.10, 0.40)
    p.box(0, -0.24, 0.72, 0.34, 0.03, 0.05)
    return [(p, "metal_dark")]


def p_news_box():
    p = Part()
    p.box(0, 0, 0.55, 0.42, 0.38, 0.72)
    p.box(0, -0.20, 0.72, 0.30, 0.02, 0.26)
    p.box(0, 0, 0.94, 0.44, 0.40, 0.05)
    return [(p, "car_paint_blue")]


def p_bus_shelter():
    p = Part()
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box(sx * 1.55, sy * 0.65, 1.25, 0.09, 0.09, 2.50)
    p.box(0, 0, 2.55, 3.40, 1.60, 0.12)
    p.box(0, 0.62, 1.30, 3.20, 0.05, 2.20)
    p.box(0, 0.30, 0.48, 2.60, 0.42, 0.06)
    p.box(1.40, 0.0, 1.30, 0.06, 1.20, 2.10)
    return [(p, "metal_dark")]


def p_bike_rack():
    p = Part()
    for i in range(3):
        x = -0.45 + i * 0.45
        p.box(x, 0, 0.45, 0.05, 0.05, 0.90)
        p.box(x, 0, 0.90, 0.05, 0.45, 0.05)
        p.box(x, 0.22, 0.68, 0.05, 0.05, 0.45)
    return [(p, "metal_galv")]


def p_bicycle():
    p = Part()
    for sx in (-1, 1):
        p.cyl(sx * 0.55, 0, 0.34, 0.34, 0.05, 14, rot=(math.pi * 0.5, 0, 0))
    p.box(0, 0, 0.55, 0.90, 0.05, 0.05)
    p.box(-0.1, 0, 0.72, 0.05, 0.05, 0.40)
    p.box(0.42, 0, 0.85, 0.05, 0.42, 0.05)
    p.box(-0.35, 0, 0.95, 0.22, 0.08, 0.05)
    return [(p, "metal_dark")]


def p_scooter():
    p = Part()
    p.box(0, 0, 0.14, 0.75, 0.16, 0.05)
    p.cyl(-0.32, 0, 0.10, 0.10, 0.05, 10, rot=(math.pi * 0.5, 0, 0))
    p.cyl(0.32, 0, 0.10, 0.10, 0.05, 10, rot=(math.pi * 0.5, 0, 0))
    p.box(0.30, 0, 0.55, 0.05, 0.05, 0.85)
    p.box(0.30, 0, 0.98, 0.05, 0.40, 0.04)
    return [(p, "metal_galv")]


def p_phone_booth():
    p = Part()
    p.box(0, 0, 1.10, 0.95, 0.95, 2.20)
    p.box(0, -0.49, 1.20, 0.80, 0.03, 1.70)
    p.box(0, 0, 2.24, 1.02, 1.02, 0.10)
    return [(p, "glass_dirty")]


def p_atm():
    p = Part()
    p.box(0, 0, 0.85, 0.80, 0.55, 1.70)
    p.box(0, -0.29, 1.25, 0.45, 0.03, 0.35)
    p.box(0, -0.29, 0.95, 0.50, 0.03, 0.10)
    return [(p, "metal_dark")]


def p_vending():
    p = Part()
    p.box(0, 0, 0.90, 0.95, 0.70, 1.80)
    p.box(0, -0.36, 1.05, 0.70, 0.03, 1.10)
    return [(p, "car_paint_red")]


def p_parking_meter():
    p = Part()
    p.cyl(0, 0, 0.55, 0.045, 1.10, 8)
    p.box(0, 0, 1.18, 0.16, 0.12, 0.26)
    p.box(0, -0.07, 1.20, 0.10, 0.02, 0.10)
    return [(p, "metal_galv")]


def p_cone():
    p = Part()
    p.box(0, 0, 0.03, 0.42, 0.42, 0.06)
    p.cyl(0, 0, 0.36, 0.16, 0.62, 10, rtop=0.03)
    return [(p, "car_paint_red")]


def p_jersey_barrier():
    p = Part()
    p.box(0, 0, 0.16, 2.00, 0.60, 0.32)
    p.box(0, 0, 0.52, 1.90, 0.34, 0.42)
    p.box(0, 0, 0.78, 1.80, 0.22, 0.14)
    return [(p, "concrete")]


def p_barricade():
    p = Part()
    for sx in (-1, 1):
        p.box(sx * 0.85, 0, 0.35, 0.08, 0.55, 0.70)
        p.box(sx * 0.85, 0, 0.05, 0.08, 0.70, 0.08)
    p.box(0, 0, 0.62, 2.10, 0.06, 0.28)
    p.box(0, 0, 0.30, 2.10, 0.05, 0.10)
    return [(p, "paint_yellow")]


def p_scaffold():
    p = Part()
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(sx * 1.4, sy * 0.7, 2.0, 0.05, 4.0, 8)
    for z in (1.0, 2.0, 3.0):
        p.box(0, -0.7, z, 2.9, 0.05, 0.05)
        p.box(0, 0.7, z, 2.9, 0.05, 0.05)
        p.box(-1.4, 0, z, 0.05, 1.5, 0.05)
        p.box(1.4, 0, z, 0.05, 1.5, 0.05)
    p.box(0, 0, 2.05, 2.8, 1.4, 0.06)
    return [(p, "metal_galv")]


def p_portable_toilet():
    p = Part()
    p.box(0, 0, 1.10, 1.10, 1.10, 2.20)
    p.box(0, -0.56, 1.10, 0.80, 0.03, 1.90)
    p.box(0, 0, 2.24, 1.18, 1.18, 0.10)
    return [(p, "car_paint_blue")]


def p_planter():
    p = Part()
    p.box(0, 0, 0.30, 1.20, 1.20, 0.60)
    p.box(0, 0, 0.62, 1.05, 1.05, 0.04)
    p2 = Part()
    p2.sphere(0, 0, 0.95, 0.55, 2, scale=(1.0, 1.0, 0.8))
    return [(p, "concrete"), (p2, "foliage")]


def p_fountain():
    p = Part()
    p.cyl(0, 0, 0.30, 1.60, 0.60, 20)
    p.cyl(0, 0, 0.62, 1.45, 0.06, 20)
    p.cyl(0, 0, 0.95, 0.35, 0.70, 12)
    p.cyl(0, 0, 1.32, 0.75, 0.10, 16)
    p2 = Part()
    p2.cyl(0, 0, 0.66, 1.40, 0.04, 20)
    return [(p, "stone"), (p2, "water")]


def p_statue():
    p = Part()
    p.box(0, 0, 0.45, 1.40, 1.40, 0.90)
    p.box(0, 0, 0.95, 1.10, 1.10, 0.12)
    p.cyl(0, 0, 1.55, 0.26, 1.10, 10)
    p.sphere(0, 0, 2.20, 0.20, 2)
    p.box(0.28, 0, 1.80, 0.60, 0.12, 0.12)
    return [(p, "stone_dark")]


def p_flagpole():
    p = Part()
    p.cyl(0, 0, 0.15, 0.22, 0.30, 12)
    p.cyl(0, 0, 3.00, 0.06, 5.70, 8)
    p.box(0.55, 0, 5.10, 1.10, 0.02, 0.65)
    return [(p, "metal_galv")]


def p_street_clock():
    p = Part()
    p.cyl(0, 0, 1.60, 0.07, 3.20, 8)
    p.cyl(0, 0, 3.35, 0.42, 0.16, 16, rot=(math.pi * 0.5, 0, 0))
    p.cyl(0, -0.09, 3.35, 0.34, 0.03, 16, rot=(math.pi * 0.5, 0, 0))
    return [(p, "metal_dark")]


PROPS = [
    (p_trash_can, 10), (p_recycling_bin, 5), (p_dumpster, 3),
    (p_bench, 6), (p_picnic_table, 2), (p_bollard, 8),
    (p_hydrant, 5), (p_mailbox, 3), (p_news_box, 4),
    (p_bus_shelter, 2), (p_bike_rack, 4), (p_bicycle, 5),
    (p_scooter, 4), (p_phone_booth, 1), (p_atm, 2),
    (p_vending, 2), (p_parking_meter, 6), (p_cone, 5),
    (p_jersey_barrier, 3), (p_barricade, 3), (p_scaffold, 1),
    (p_portable_toilet, 1), (p_planter, 6), (p_fountain, 1),
    (p_statue, 1), (p_flagpole, 2), (p_street_clock, 1),
]


# -----------------------------------------------------------------------------
def _edge_slots(b, R, n):
    x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]
    out = []
    for _ in range(n):
        side = R.choice(["S", "S", "N", "E", "W"])
        if side == "S":
            out.append((R.uniform(x0 + 2.0, x1 - 2.0), y0 + 1.7, 0.0))
        elif side == "N":
            out.append((R.uniform(x0 + 2.0, x1 - 2.0), y1 - 1.7, math.pi))
        elif side == "W":
            out.append((x0 + 1.7, R.uniform(y0 + 2.0, y1 - 2.0), math.pi * 0.5))
        else:
            out.append((x1 - 1.7, R.uniform(y0 + 2.0, y1 - 2.0), -math.pi * 0.5))
    return out


def _weighted_pick(R):
    total = sum(w for _, w in PROPS)
    t = R.uniform(0, total)
    acc = 0.0
    for fn, w in PROPS:
        acc += w
        if t <= acc:
            return fn
    return PROPS[0][0]


def build():
    collection = C.col("CITY_Props")
    R = rng("props")
    plan = plan_city()
    tree_pits = C.get_asset("tree_pits", [])
    detail = 1.0 if CONFIG["quality"] == "high" else 0.65

    count = 0
    for b in plan["blocks"]:
        if b["district"] == "parkland":
            continue
        n = int(R.uniform(2, 7) * detail) + 1
        for (x, y, rot) in _edge_slots(b, R, n):
            if any((x - tx) ** 2 + (y - ty) ** 2 < 1.6 ** 2 for (tx, ty) in tree_pits):
                continue
            fn = _weighted_pick(R)
            for part, mat in fn():
                part.obj("Prop_{:04d}".format(count), mat, collection,
                         loc=(x, y, BASE_Z), rot=rot)
            count += 1

    # a few hero props in the park blocks
    for p in plan["parks"]:
        cx, cy = p["cx"], p["cy"]
        for part, mat in p_fountain():
            part.obj("Park_Fountain", mat, collection, loc=(cx, cy, BASE_Z))
        for i in range(3):
            for part, mat in p_bench():
                part.obj("Park_Bench_{}".format(i), mat, collection,
                         loc=(cx + R.uniform(-8, 8), cy + R.uniform(-8, 8), BASE_Z),
                         rot=R.uniform(0, math.tau))

    print("  props placed: {}".format(count))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="M9 PROPS")
    C.build_all_materials()
    build()
    C.report()