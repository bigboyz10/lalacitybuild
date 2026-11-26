# =============================================================================
#  CITY BUILD  --  M10 : UTILITIES, POLES, WIRES, TRAFFIC SIGNALS
#  standalone:  blender -b -P utilities.py -- --quality preview
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
def add_wire(bm, p0, p1, sag=0.55, r=0.022, seg=10):
    (x0, y0, z0), (x1, y1, z1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1.0
    px, py = -dy / ln, dx / ln
    rings = []
    for i in range(seg + 1):
        t = i / seg
        x = x0 + dx * t
        y = y0 + dy * t
        z = z0 + (z1 - z0) * t - sag * 4.0 * t * (1.0 - t)
        ring = []
        for (a, b) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            ring.append(bm.verts.new((x + px * r * a, y + py * r * a, z + r * b)))
        rings.append(ring)
    for i in range(seg):
        a, b = rings[i], rings[i + 1]
        for k in range(4):
            k2 = (k + 1) % 4
            bm.faces.new((a[k], a[k2], b[k2], b[k]))


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


# -----------------------------------------------------------------------------
def build():
    collection = C.col("CITY_Utilities")
    R = rng("utilities")
    plan = plan_city()
    segs = roads._segments(plan)
    detail = 1.0 if CONFIG["quality"] == "high" else 0.7

    # ---------------- utility poles + catenary wires
    pole_groups = {}
    n_poles = 0
    for s in segs:
        if s["kind"] == "arterial":
            continue
        if R.random() > 0.55:
            continue
        L = s["b"] - s["a"]
        if L < 20.0:
            continue
        side = 1 if R.random() < 0.5 else -1
        off = side * (s["w"] * 0.5 + 0.75)
        along = s["a"] + 6.0
        while along < s["b"] - 4.0:
            if s["axis"] == "ns":
                x, y = s["c"] + off, along
            else:
                x, y = along, s["c"] + off
            p = Part()
            p.cyl(0, 0, 4.6, 0.11, 9.0, 8)
            p.box(0, 0, 8.35, 2.2, 0.10, 0.10)
            p.box(0, 0, 7.55, 1.4, 0.09, 0.09)
            for sx in (-0.9, 0.0, 0.9):
                p.cyl(sx, 0, 8.52, 0.05, 0.16, 6)
            if R.random() < 0.35:
                p.cyl(0.28, 0, 6.9, 0.24, 0.70, 10)
            p.obj("UtilityPole_{:04d}".format(n_poles), "wood", collection,
                  loc=(x, y, BASE_Z))
            key = (s["axis"], round(s["c"], 3), side)
            pole_groups.setdefault(key, []).append((along, x, y))
            n_poles += 1
            along += R.uniform(28.0, 38.0)

    bm_wire = bmesh.new()
    n_wires = 0
    for key, poles in pole_groups.items():
        poles.sort()
        for i in range(len(poles) - 1):
            _, x0, y0 = poles[i]
            _, x1, y1 = poles[i + 1]
            for k, (ox, oz) in enumerate(((-0.9, 8.45), (0.0, 8.45), (0.9, 8.45))):
                add_wire(bm_wire, (x0 + ox * 0.4, y0, BASE_Z + oz),
                         (x1 + ox * 0.4, y1, BASE_Z + oz),
                         sag=0.55 + k * 0.05, r=0.02)
                n_wires += 1
    _mesh("Utility_Wires", bm_wire, "metal_dark", collection)

    # ---------------- street lights on arterials
    n_street = 0
    for s in segs:
        if s["kind"] != "arterial":
            continue
        L = s["b"] - s["a"]
        side = 1 if R.random() < 0.5 else -1
        off = side * (s["w"] * 0.5 + 0.55)
        along = s["a"] + 8.0
        while along < s["b"] - 6.0:
            if s["axis"] == "ns":
                x, y = s["c"] + off, along
                rot = 0.0 if side > 0 else math.pi
            else:
                x, y = along, s["c"] + off
                rot = math.pi * 0.5 if side > 0 else -math.pi * 0.5
            p = Part()
            p.cyl(0, 0, 4.5, 0.09, 9.0, 8)
            p.box(0, 0, 8.95, 2.4, 0.12, 0.12)
            p.box(1.15, 0, 8.80, 0.85, 0.34, 0.16)
            p.obj("StreetLight_{:04d}".format(n_street), "metal_galv",
                  collection, loc=(x, y, BASE_Z), rot=rot)
            p2 = Part()
            p2.box(1.15, 0, 8.70, 0.70, 0.26, 0.04)
            p2.obj("StreetLightGlow_{:04d}".format(n_street), "lamp_warm",
                   collection, loc=(x, y, BASE_Z), rot=rot)
            n_street += 1
            along += R.uniform(26.0, 34.0)

    # ---------------- decorative lamps in residential blocks
    n_deco = 0
    for b in plan["blocks"]:
        if b["district"] not in ("residential", "midtown"):
            continue
        if R.random() > 0.5:
            continue
        x = b["x0"] + 1.2
        y = b["y0"] + R.uniform(4.0, max(4.2, b["h"] - 4.0))
        p = Part()
        p.cyl(0, 0, 2.1, 0.06, 4.2, 8)
        p.cyl(0, 0, 4.35, 0.16, 0.30, 8)
        p.box(0, 0, 0.12, 0.30, 0.30, 0.24)
        p.obj("DecorLamp_{:04d}".format(n_deco), "metal_dark", collection,
              loc=(x, y, BASE_Z))
        p2 = Part()
        p2.cyl(0, 0, 4.35, 0.13, 0.22, 8)
        p2.obj("DecorLampGlow_{:04d}".format(n_deco), "lamp_warm", collection,
               loc=(x, y, BASE_Z))
        n_deco += 1

    # ---------------- traffic signals at intersections
    n_sig = 0
    for it in plan["intersections"]:
        if R.random() > 0.75 * detail + 0.2:
            continue
        cx, cy = it["x"], it["y"]
        wns, wew = it["w"], it["h"]
        for (sx, sy) in ((1, 1), (-1, -1)):
            px = cx + sx * (wns * 0.5 + 0.9)
            py = cy + sy * (wew * 0.5 + 0.9)
            arm = 4.2 * sx
            p = Part()
            p.cyl(0, 0, 3.2, 0.11, 6.4, 8)
            p.box(arm * 0.5, 0, 6.30, abs(arm), 0.12, 0.12)
            p.box(arm, 0, 5.95, 0.34, 0.30, 1.05)
            p.obj("TrafficPole_{:04d}".format(n_sig), "metal_galv",
                  collection, loc=(px, py, BASE_Z))
            for k, (mat, dz) in enumerate((("traffic_red", 0.34),
                                           ("traffic_amber", 0.0),
                                           ("traffic_green", -0.34))):
                p2 = Part()
                p2.cyl(arm, -0.16, 5.95 + dz, 0.11, 0.05, 10,
                       rot=(math.pi * 0.5, 0, 0))
                p2.obj("TrafficLens_{:04d}_{}".format(n_sig, k), mat,
                       collection, loc=(px, py, BASE_Z))
            # pedestrian signal on the pole
            p3 = Part()
            p3.box(0.16, 0, 2.60, 0.26, 0.18, 0.34)
            p3.obj("PedSignal_{:04d}".format(n_sig), "metal_dark",
                   collection, loc=(px, py, BASE_Z))
            n_sig += 1

    # ---------------- fire alarm + junction cabinets
    n_cab = 0
    for b in plan["blocks"]:
        if R.random() > 0.4:
            continue
        x = b["x0"] + R.uniform(1.0, 2.4)
        y = b["y0"] + R.uniform(3.0, max(3.2, b["h"] - 3.0))
        p = Part()
        p.box(0, 0, 0.55, 0.42, 0.30, 0.80)
        p.box(0, -0.16, 0.72, 0.30, 0.03, 0.22)
        p.obj("JunctionBox_{:04d}".format(n_cab), "metal_galv", collection,
              loc=(x, y, BASE_Z))
        n_cab += 1

    # ---------------- rooftop cell towers
    n_tower = 0
    for b in C.get_asset("buildings", []):
        if not b or b["height"] < 35.0:
            continue
        if R.random() > 0.12:
            continue
        x0, y0, x1, y1 = b["rect"]
        x = (x0 + x1) * 0.5 + R.uniform(-3, 3)
        y = (y0 + y1) * 0.5 + R.uniform(-3, 3)
        z = BASE_Z + b["height"]
        p = Part()
        for sx in (-1, 1):
            for sy in (-1, 1):
                p.cyl(sx * 0.55, sy * 0.55, 3.0, 0.06, 6.0, 6)
        for k in range(4):
            p.box(0, 0, 1.0 + k * 1.4, 1.3, 1.3, 0.05)
        p.box(0, 0, 6.2, 0.9, 0.9, 0.08)
        p.obj("CellTower_{:04d}".format(n_tower), "metal_galv", collection,
              loc=(x, y, z))
        n_tower += 1

    print("  poles: {}  wires: {}  street lights: {}  deco lamps: {}  signals: {}  cabinets: {}  towers: {}".format(
        n_poles, n_wires, n_street, n_deco, n_sig, n_cab, n_tower))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="M10 UTILITIES")
    C.build_all_materials()
    build()
    C.report()