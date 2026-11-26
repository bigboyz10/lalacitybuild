# =============================================================================
#  CITY BUILD  --  ENHANCE : POST-CRITIQUE ADDITIONS
#  construction cranes, food carts, chain-link fences, newspaper stands,
#  dirt/sand piles, construction barriers
#  standalone:  blender -b -P enhance.py -- --quality preview
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

    def cyl(self, cx=0.0, cy=0.0, cz=0.0, r=0.5, depth=1.0, seg=8,
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


def _extra_materials():
    C.make_pbr("chainlink", base="#8d9296", roughness=0.55, metallic=0.75,
               bump=0.20, bump_scale=24, var_noise=7, grime=0.4, alpha=0.55)
    C.make_pbr("dirt_pile", base="#5b4a37", roughness=0.97, bump=0.50,
               bump_scale=10, var_noise=8, grime=0.3)
    C.make_pbr("sand_pile", base="#b8a271", roughness=0.97, bump=0.45,
               bump_scale=12, var_noise=9, grime=0.25)


# -----------------------------------------------------------------------------
def crane(name, x, y, rot, collection, h=34.0):
    p = Part()
    # lattice mast
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box(sx * 0.55, sy * 0.55, h * 0.5, 0.16, 0.16, h)
    for k in range(int(h / 2.0)):
        z = 1.0 + k * 2.0
        p.box(0, -0.55, z, 1.2, 0.10, 0.10)
        p.box(0, 0.55, z, 1.2, 0.10, 0.10)
        p.box(-0.55, 0, z, 0.10, 1.2, 0.10)
        p.box(0.55, 0, z, 0.10, 1.2, 0.10)
    # jib + counter jib
    p.box(6.0, 0, h + 0.4, 16.0, 0.9, 0.9)
    p.box(-4.0, 0, h + 0.4, 6.0, 1.1, 1.1)
    p.box(0, 0, h + 1.6, 0.7, 0.7, 2.2)
    # cabin
    p.box(-1.6, 0, h - 1.0, 1.8, 1.6, 1.8)
    # hook line
    p.box(13.0, 0, h - 4.0, 0.06, 0.06, 8.0)
    p.box(13.0, 0, h - 8.2, 0.5, 0.5, 0.6)
    p.obj(name, "paint_yellow", collection, loc=(x, y, BASE_Z), rot=rot)
    # counterweight
    p2 = Part()
    p2.box(-6.6, 0, h + 0.4, 1.6, 2.0, 1.6)
    p2.obj(name + "_Counterweight", "concrete", collection,
           loc=(x, y, BASE_Z), rot=rot)


def food_cart(name, x, y, rot, collection):
    p = Part()
    p.box(0, 0, 0.75, 1.9, 0.95, 0.55)
    p.box(0, 0, 1.06, 2.0, 1.05, 0.06)
    for sx in (-1, 1):
        p.cyl(sx * 0.7, 0, 0.28, 0.28, 0.10, 10, rot=(math.pi * 0.5, 0, 0))
    p.cyl(0, 0, 1.9, 0.05, 1.7, 6)
    p.cyl(0, 0, 2.75, 1.35, 0.35, 12, rtop=0.05)
    p.obj(name, "metal_galv", collection, loc=(x, y, BASE_Z), rot=rot)
    p2 = Part()
    p2.cyl(0, 0, 2.72, 1.30, 0.30, 12, rtop=0.05)
    p2.obj(name + "_Umbrella", "fabric_red", collection,
           loc=(x, y, BASE_Z), rot=rot)


def chainlink_fence(name, x0, y0, x1, y1, collection, h=2.4):
    p = Part()
    length = math.hypot(x1 - x0, y1 - y0)
    ang = math.atan2(y1 - y0, x1 - x0)
    n = max(2, int(length / 2.4))
    for i in range(n + 1):
        t = i / n
        px = x0 + (x1 - x0) * t
        py = y0 + (y1 - y0) * t
        p.cyl(px, py, h * 0.5, 0.05, h, 6)
    p.box((x0 + x1) * 0.5, (y0 + y1) * 0.5, h - 0.05, length, 0.05, 0.05, ang)
    p.obj(name + "_Posts", "metal_galv", collection)
    p2 = Part()
    ca, sa = math.cos(ang), math.sin(ang)
    hw = length * 0.5
    vs = [p2.bm.verts.new(((x0 + x1) * 0.5 - hw * ca, (y0 + y1) * 0.5 - hw * sa, BASE_Z + 0.1)),
          p2.bm.verts.new(((x0 + x1) * 0.5 + hw * ca, (y0 + y1) * 0.5 + hw * sa, BASE_Z + 0.1)),
          p2.bm.verts.new(((x0 + x1) * 0.5 + hw * ca, (y0 + y1) * 0.5 + hw * sa, BASE_Z + h - 0.1)),
          p2.bm.verts.new(((x0 + x1) * 0.5 - hw * ca, (y0 + y1) * 0.5 - hw * sa, BASE_Z + h - 0.1))]
    p2.bm.faces.new(vs)
    p2.obj(name + "_Mesh", "chainlink", collection)


def newspaper_stand(name, x, y, rot, collection):
    p = Part()
    p.box(0, 0, 0.55, 1.10, 0.60, 1.10)
    p.box(0, -0.31, 0.85, 0.90, 0.03, 0.45)
    p.box(0, 0, 1.14, 1.18, 0.68, 0.06)
    p.obj(name, "car_paint_blue", collection, loc=(x, y, BASE_Z), rot=rot)


def dirt_pile(name, x, y, r, collection, mat="dirt_pile"):
    p = Part()
    p.cyl(0, 0, r * 0.45, r, r * 0.9, 12, rtop=r * 0.15)
    p.obj(name, mat, collection, loc=(x, y, BASE_Z))


# -----------------------------------------------------------------------------
def build():
    _extra_materials()
    collection = C.col("CITY_Enhance")
    R = rng("enhance")
    plan = plan_city()

    n_crane = n_cart = n_fence = n_news = n_pile = 0

    # construction cranes on two large blocks
    cands = [b for b in plan["blocks"]
             if b["district"] in ("midtown", "downtown") and b["w"] > 40 and b["h"] > 40]
    for b in cands[:2]:
        crane("Crane_{}".format(n_crane), b["cx"] + 6.0, b["cy"] - 6.0,
              R.uniform(0, math.tau), collection, h=R.uniform(28, 40))
        n_crane += 1
        dirt_pile("DirtPile_{}".format(n_crane), b["cx"] - 8.0, b["cy"] + 6.0,
                  R.uniform(2.5, 4.5), collection)
        n_pile += 1
        chainlink_fence("Fence_{}".format(n_crane),
                        b["x0"] + 1.0, b["y0"] + 1.0,
                        b["x1"] - 1.0, b["y0"] + 1.0, collection)
        n_fence += 1

    # food carts + newspaper stands on busy sidewalks
    for b in plan["blocks"]:
        if b["district"] == "parkland":
            continue
        if R.random() < 0.30:
            x = R.uniform(b["x0"] + 3.0, b["x1"] - 3.0)
            y = b["y0"] + 2.2
            food_cart("FoodCart_{}".format(n_cart), x, y, R.uniform(0, math.tau), collection)
            n_cart += 1
        if R.random() < 0.22:
            x = R.uniform(b["x0"] + 3.0, b["x1"] - 3.0)
            y = b["y1"] - 2.2
            newspaper_stand("NewsStand_{}".format(n_news), x, y,
                            R.uniform(0, math.tau), collection)
            n_news += 1

    # sand piles near the industrial belt
    for b in plan["blocks"]:
        if b["district"] != "industrial":
            continue
        if R.random() < 0.5:
            dirt_pile("SandPile_{}".format(n_pile),
                      R.uniform(b["x0"] + 4, b["x1"] - 4),
                      R.uniform(b["y0"] + 4, b["y1"] - 4),
                      R.uniform(1.8, 3.4), collection, mat="sand_pile")
            n_pile += 1

    print("  cranes: {}  food carts: {}  fences: {}  news stands: {}  piles: {}".format(
        n_crane, n_cart, n_fence, n_news, n_pile))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="ENHANCE")
    C.build_all_materials()
    build()
    C.report()