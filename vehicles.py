# =============================================================================
#  CITY BUILD  --  M11 : VEHICLES & TRAFFIC
#  standalone:  blender -b -P vehicles.py -- --quality preview
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
import roads

BASE_Z = 0.15
ROAD_Z = 0.02


class Part:
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

    def cyl(self, cx=0.0, cy=0.0, cz=0.0, r=0.5, depth=1.0, seg=10,
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

    def obj(self, name, mat, collection, loc=(0, 0, 0), rot=0.0):
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
        return ob


# -----------------------------------------------------------------------------
def _wheels(p, L, W, r=0.33, width=0.22):
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(sx * L * 0.32, sy * (W * 0.5 - 0.06), r, r, width, 12,
                  rot=(math.pi * 0.5, 0, 0))


def vehicle_sedan(color):
    L, W = 4.55, 1.86
    body = Part()
    body.box(0, 0, 0.62, L, W, 0.52)
    body.box(-0.15, 0, 0.95, L * 0.52, W * 0.92, 0.34)
    body.box(0, 0, 0.36, L * 0.96, W * 0.98, 0.18)
    glass = Part()
    glass.box(-0.15, 0, 1.00, L * 0.50, W * 0.86, 0.26)
    wheels = Part()
    _wheels(wheels, L, W)
    lights = Part()
    lights.box(L * 0.5 - 0.03, 0, 0.68, 0.06, W * 0.72, 0.16)
    return [(body, color), (glass, "glass_dirty"), (wheels, "rubber"),
            (lights, "lamp_warm")]


def vehicle_suv(color):
    L, W = 4.85, 1.98
    body = Part()
    body.box(0, 0, 0.72, L, W, 0.66)
    body.box(-0.10, 0, 1.18, L * 0.58, W * 0.94, 0.52)
    glass = Part()
    glass.box(-0.10, 0, 1.22, L * 0.55, W * 0.88, 0.40)
    wheels = Part()
    _wheels(wheels, L, W, r=0.38, width=0.26)
    lights = Part()
    lights.box(L * 0.5 - 0.03, 0, 0.80, 0.06, W * 0.70, 0.18)
    return [(body, color), (glass, "glass_dirty"), (wheels, "rubber"),
            (lights, "lamp_warm")]


def vehicle_pickup(color):
    L, W = 5.40, 2.02
    body = Part()
    body.box(0, 0, 0.70, L, W, 0.58)
    body.box(L * 0.16, 0, 1.18, L * 0.34, W * 0.96, 0.62)
    body.box(-L * 0.28, 0, 1.02, L * 0.40, W * 0.94, 0.30)
    glass = Part()
    glass.box(L * 0.16, 0, 1.24, L * 0.32, W * 0.88, 0.44)
    wheels = Part()
    _wheels(wheels, L, W, r=0.40, width=0.28)
    lights = Part()
    lights.box(L * 0.5 - 0.03, 0, 0.78, 0.06, W * 0.70, 0.20)
    return [(body, color), (glass, "glass_dirty"), (wheels, "rubber"),
            (lights, "lamp_warm")]


def vehicle_van(color):
    L, W = 5.30, 2.05
    body = Part()
    body.box(0, 0, 1.15, L, W, 1.70)
    body.box(L * 0.34, 0, 0.85, L * 0.22, W * 0.96, 0.90)
    glass = Part()
    glass.box(L * 0.40, 0, 1.35, 0.06, W * 0.80, 0.55)
    wheels = Part()
    _wheels(wheels, L, W, r=0.36)
    lights = Part()
    lights.box(L * 0.5 - 0.03, 0, 0.80, 0.06, W * 0.66, 0.20)
    return [(body, color), (glass, "glass_dirty"), (wheels, "rubber"),
            (lights, "lamp_warm")]


def vehicle_bus():
    L, W = 11.5, 2.55
    body = Part()
    body.box(0, 0, 1.55, L, W, 2.60)
    glass = Part()
    glass.box(0, 0, 2.05, L * 0.94, W * 1.005, 0.95)
    wheels = Part()
    _wheels(wheels, L, W, r=0.48, width=0.30)
    lights = Part()
    lights.box(L * 0.5 - 0.03, 0, 0.85, 0.06, W * 0.70, 0.22)
    return [(body, "car_paint_white"), (glass, "glass_dirty"),
            (wheels, "rubber"), (lights, "lamp_warm")]


def vehicle_box_truck():
    L, W = 7.20, 2.35
    body = Part()
    body.box(L * 0.30, 0, 1.20, L * 0.34, W * 0.96, 1.90)
    body.box(-L * 0.16, 0, 1.55, L * 0.56, W, 2.60)
    glass = Part()
    glass.box(L * 0.44, 0, 1.55, 0.06, W * 0.80, 0.60)
    wheels = Part()
    _wheels(wheels, L, W, r=0.44, width=0.30)
    lights = Part()
    lights.box(L * 0.5 - 0.03, 0, 0.85, 0.06, W * 0.66, 0.22)
    return [(body, "car_paint_white"), (glass, "glass_dirty"),
            (wheels, "rubber"), (lights, "lamp_warm")]


def vehicle_service(color, box_h=2.4):
    L, W = 7.60, 2.45
    body = Part()
    body.box(L * 0.30, 0, 1.25, L * 0.36, W * 0.96, 2.00)
    body.box(-L * 0.14, 0, 1.45, L * 0.56, W, box_h)
    glass = Part()
    glass.box(L * 0.45, 0, 1.60, 0.06, W * 0.80, 0.62)
    wheels = Part()
    _wheels(wheels, L, W, r=0.46, width=0.32)
    lights = Part()
    lights.box(L * 0.5 - 0.03, 0, 0.90, 0.06, W * 0.66, 0.24)
    lights.box(0, 0, 1.25 + box_h * 0.5 + 0.12, 1.2, 0.28, 0.16)
    return [(body, color), (glass, "glass_dirty"), (wheels, "rubber"),
            (lights, "lamp_warm")]


def vehicle_motorcycle():
    body = Part()
    body.box(0, 0, 0.62, 1.10, 0.42, 0.34)
    body.cyl(-0.62, 0, 0.34, 0.32, 0.10, 12, rot=(math.pi * 0.5, 0, 0))
    body.cyl(0.62, 0, 0.34, 0.32, 0.10, 12, rot=(math.pi * 0.5, 0, 0))
    body.box(0.42, 0, 0.92, 0.06, 0.06, 0.60)
    body.box(0.42, 0, 1.18, 0.06, 0.44, 0.05)
    return [(body, "metal_dark")]


KINDS = [
    ("sedan", 26, lambda: vehicle_sedan(C.M("car_paint_silver"))),
    ("sedan", 14, lambda: vehicle_sedan(C.M("car_paint_black"))),
    ("sedan", 10, lambda: vehicle_sedan(C.M("car_paint_blue"))),
    ("sedan", 8, lambda: vehicle_sedan(C.M("car_paint_red"))),
    ("suv", 14, lambda: vehicle_suv(C.M("car_paint_black"))),
    ("suv", 8, lambda: vehicle_suv(C.M("car_paint_white"))),
    ("pickup", 8, lambda: vehicle_pickup(C.M("car_paint_blue"))),
    ("van", 7, lambda: vehicle_van(C.M("car_paint_white"))),
    ("taxi", 10, lambda: vehicle_sedan(C.M("car_paint_taxi"))),
    ("bus", 3, vehicle_bus),
    ("box", 4, vehicle_box_truck),
    ("garbage", 2, lambda: vehicle_service(C.M("car_paint_green"))),
    ("fire", 1, lambda: vehicle_service(C.M("car_paint_red"), 2.6)),
    ("ambulance", 1, lambda: vehicle_service(C.M("car_paint_white"), 2.2)),
    ("police", 3, lambda: vehicle_sedan(C.M("car_paint_black"))),
    ("moto", 5, vehicle_motorcycle),
]


def _pick(R):
    total = sum(w for _, w, _ in KINDS)
    t = R.uniform(0, total)
    acc = 0.0
    for kind, w, fn in KINDS:
        acc += w
        if t <= acc:
            return kind, fn
    return KINDS[0][0], KINDS[0][2]


def _place(name, parts, collection, x, y, rot, z=ROAD_Z, flat=False):
    for part, mat in parts:
        part.obj(name, mat, collection, loc=(x, y, z), rot=rot)


# -----------------------------------------------------------------------------
def build():
    collection = C.col("CITY_Vehicles")
    R = rng("vehicles")
    plan = plan_city()
    segs = roads._segments(plan)
    detail = 1.0 if CONFIG["quality"] == "high" else 0.7

    count = 0
    abandoned = 0

    # ---- parked cars along block edges
    for b in plan["blocks"]:
        if b["district"] == "parkland":
            continue
        x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]
        for side in ("S", "N"):
            x = x0 + 4.0
            while x < x1 - 4.0:
                if R.random() < 0.55 * detail:
                    kind, fn = _pick(R)
                    y = y0 - 1.15 if side == "S" else y1 + 1.15
                    rot = 0.0 if side == "S" else math.pi
                    _place("Parked_{:04d}".format(count), fn(), collection,
                           x, y, rot)
                    count += 1
                x += R.uniform(6.0, 9.0)

    # ---- moving traffic in the lanes
    for s in segs:
        L = s["b"] - s["a"]
        if L < 16.0:
            continue
        lanes = max(1, int(s["w"] // 3.0))
        n = int(L / 34.0 * detail) + (1 if R.random() < 0.3 else 0)
        for i in range(n):
            kind, fn = _pick(R)
            along = s["a"] + R.uniform(3.0, max(3.2, L - 3.0))
            lane = R.randint(0, lanes - 1)
            off = -s["w"] * 0.5 + 1.5 + lane * 3.0
            if s["axis"] == "ns":
                x, y = s["c"] + off, along
                rot = 0.0 if R.random() < 0.5 else math.pi
                rot = math.pi * 0.5 if rot == 0.0 else -math.pi * 0.5
            else:
                x, y = along, s["c"] + off
                rot = 0.0 if R.random() < 0.5 else math.pi
            _place("Traffic_{:04d}".format(count), fn(), collection, x, y, rot)
            count += 1

    # ---- abandoned / stripped cars in the industrial belt
    for b in plan["blocks"]:
        if b["district"] != "industrial":
            continue
        for i in range(R.randint(0, 3)):
            kind, fn = _pick(R)
            x = R.uniform(b["x0"] + 3.0, b["x1"] - 3.0)
            y = R.uniform(b["y0"] + 3.0, b["y1"] - 3.0)
            _place("Abandoned_{:04d}".format(abandoned), fn(), collection,
                   x, y, R.uniform(0, math.tau), z=BASE_Z)
            abandoned += 1

    print("  vehicles: {}  (abandoned: {})".format(count, abandoned))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="M11 VEHICLES")
    C.build_all_materials()
    build()
    C.report()