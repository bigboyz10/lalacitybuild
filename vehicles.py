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
def _loft(part, sections, taper_ends=True):
    """Build a closed hull through ordered cross-sections.

    Each section is (x, half_width, z_bottom, z_top).  Lofting these gives a
    real car silhouette - sloped bonnet, curved roofline, tapered tail - for
    roughly the same triangle count as the stacked boxes it replaces.
    """
    rings = []
    for (x, hw, z0, z1) in sections:
        ring = [
            part.bm.verts.new((x, -hw, z0)),
            part.bm.verts.new((x,  hw, z0)),
            part.bm.verts.new((x,  hw, z1)),
            part.bm.verts.new((x, -hw, z1)),
        ]
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            part.bm.faces.new((a[i], a[j], b[j], b[i]))
    if taper_ends:
        part.bm.faces.new(list(reversed(rings[0])))
        part.bm.faces.new(rings[-1])
    return part


def _arch(part, L, W, r, width):
    """Shallow wheel arches so wheels sit in a recess, not against a slab."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.box(sx * L * 0.31, sy * (W * 0.5 - width * 0.42),
                     r * 0.98, r * 2.35, width * 1.15, r * 0.30)


def _wheels(p, L, W, r=0.33, width=0.22):
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(sx * L * 0.32, sy * (W * 0.5 - 0.06), r, r, width, 12,
                  rot=(math.pi * 0.5, 0, 0))


def vehicle_sedan(color):
    L, W = 4.62, 1.84
    hl = L * 0.5
    body = Part()
    # bonnet -> windscreen -> roof -> boot, as a single lofted hull
    _loft(body, [
        (-hl,          W * 0.40, 0.46, 0.78),
        (-hl * 0.86,   W * 0.47, 0.34, 0.86),
        (-hl * 0.52,   W * 0.50, 0.30, 0.95),
        (-hl * 0.18,   W * 0.50, 0.28, 1.40),
        ( hl * 0.16,   W * 0.49, 0.28, 1.44),
        ( hl * 0.50,   W * 0.48, 0.30, 1.22),
        ( hl * 0.84,   W * 0.45, 0.34, 0.92),
        ( hl,          W * 0.38, 0.46, 0.82),
    ])
    _arch(body, L, W, 0.33, 0.22)
    glass = Part()
    # greenhouse: inset and narrower than the body, with a raked screen
    _loft(glass, [
        (-hl * 0.20, W * 0.44, 0.97, 1.36),
        ( hl * 0.02, W * 0.45, 1.00, 1.42),
        ( hl * 0.34, W * 0.44, 1.00, 1.33),
        ( hl * 0.56, W * 0.42, 0.99, 1.16),
    ])
    wheels = Part()
    _wheels(wheels, L, W)
    lights = Part()
    lights.box(-hl + 0.06, -W * 0.30, 0.70, 0.10, W * 0.26, 0.15)
    lights.box(-hl + 0.06,  W * 0.30, 0.70, 0.10, W * 0.26, 0.15)
    tail = Part()
    tail.box(hl - 0.05, -W * 0.31, 0.76, 0.08, W * 0.24, 0.13)
    tail.box(hl - 0.05,  W * 0.31, 0.76, 0.08, W * 0.24, 0.13)
    trim = Part()
    for sy in (-1, 1):
        trim.box(-hl * 0.10, sy * W * 0.52, 1.18, 0.16, 0.05, 0.09)   # mirrors
    return [(body, color), (glass, "glass_dirty"), (wheels, "rubber"),
            (lights, "lamp_warm"), (tail, "lamp_red"), (trim, "metal_dark")]


def vehicle_suv(color):
    L, W = 4.88, 1.98
    hl = L * 0.5
    body = Part()
    _loft(body, [
        (-hl,        W * 0.42, 0.52, 0.98),
        (-hl * 0.84, W * 0.48, 0.40, 1.08),
        (-hl * 0.46, W * 0.50, 0.36, 1.20),
        (-hl * 0.12, W * 0.50, 0.34, 1.80),
        ( hl * 0.30, W * 0.50, 0.34, 1.86),
        ( hl * 0.70, W * 0.49, 0.36, 1.82),
        ( hl,        W * 0.45, 0.50, 1.66),
    ])
    _arch(body, L, W, 0.38, 0.26)
    glass = Part()
    _loft(glass, [
        (-hl * 0.14, W * 0.45, 1.24, 1.74),
        ( hl * 0.16, W * 0.46, 1.26, 1.80),
        ( hl * 0.54, W * 0.45, 1.26, 1.76),
        ( hl * 0.86, W * 0.42, 1.24, 1.62),
    ])
    wheels = Part()
    _wheels(wheels, L, W, r=0.38, width=0.26)
    lights = Part()
    lights.box(-hl + 0.06, -W * 0.31, 0.88, 0.10, W * 0.26, 0.17)
    lights.box(-hl + 0.06,  W * 0.31, 0.88, 0.10, W * 0.26, 0.17)
    tail = Part()
    tail.box(hl - 0.05, -W * 0.32, 1.30, 0.08, W * 0.20, 0.26)
    tail.box(hl - 0.05,  W * 0.32, 1.30, 0.08, W * 0.20, 0.26)
    rails = Part()
    for sy in (-1, 1):
        rails.box(hl * 0.22, sy * W * 0.38, 1.90, L * 0.52, 0.07, 0.06)
    return [(body, color), (glass, "glass_dirty"), (wheels, "rubber"),
            (lights, "lamp_warm"), (tail, "lamp_red"), (rails, "metal_dark")]


def vehicle_pickup(color):
    L, W = 5.42, 2.02
    hl = L * 0.5
    body = Part()
    _loft(body, [
        (-hl,        W * 0.44, 0.52, 1.02),
        (-hl * 0.80, W * 0.49, 0.42, 1.10),
        (-hl * 0.42, W * 0.50, 0.38, 1.22),
        (-hl * 0.12, W * 0.50, 0.38, 1.88),
        ( hl * 0.08, W * 0.50, 0.38, 1.90),
        ( hl * 0.14, W * 0.50, 0.38, 1.24),
        ( hl,        W * 0.50, 0.42, 1.20),
    ])
    _arch(body, L, W, 0.40, 0.28)
    # load bed walls
    for sy in (-1, 1):
        body.box(hl * 0.56, sy * W * 0.46, 1.08, L * 0.42, W * 0.08, 0.42)
    body.box(hl - 0.07, 0.0, 1.08, 0.12, W * 0.96, 0.42)
    glass = Part()
    _loft(glass, [
        (-hl * 0.14, W * 0.45, 1.28, 1.82),
        ( hl * 0.00, W * 0.46, 1.30, 1.86),
        ( hl * 0.10, W * 0.45, 1.30, 1.84),
    ])
    wheels = Part()
    _wheels(wheels, L, W, r=0.40, width=0.28)
    lights = Part()
    lights.box(-hl + 0.06, -W * 0.32, 0.92, 0.10, W * 0.26, 0.18)
    lights.box(-hl + 0.06,  W * 0.32, 0.92, 0.10, W * 0.26, 0.18)
    tail = Part()
    tail.box(hl - 0.05, -W * 0.34, 1.02, 0.08, W * 0.18, 0.22)
    tail.box(hl - 0.05,  W * 0.34, 1.02, 0.08, W * 0.18, 0.22)
    return [(body, color), (glass, "glass_dirty"), (wheels, "rubber"),
            (lights, "lamp_warm"), (tail, "lamp_red")]


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


_LA_WEIGHT = {"taxi": 0.1, "suv": 1.6, "pickup": 1.3, "bus": 0.6,
              "garbage": 0.5, "moto": 0.7}


def _kinds():
    if not C.is_la():
        return KINDS
    return [(k, max(1, int(round(w * _LA_WEIGHT.get(k, 1.0)))), fn)
            for (k, w, fn) in KINDS]


def _pick(R):
    kinds = _kinds()
    total = sum(w for _, w, _ in kinds)
    t = R.uniform(0, total)
    acc = 0.0
    for kind, w, fn in kinds:
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
        if b["district"] != "industrial" or C.is_la():
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