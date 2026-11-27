# =============================================================================
#  CITY BUILD  --  M12 : VEGETATION
#  street trees, park trees, hedges, weeds, ivy, moss, leaf litter, stumps
#  standalone:  blender -b -P vegetation.py -- --quality preview
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
from core import CONFIG, U, rng, plan_city, add_cylinder

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
# tree variants (built once, then linked-duplicated)
# -----------------------------------------------------------------------------
def _tree_variant(name, trunk_h, trunk_r, blobs, spread, col):
    trunk = Part()
    trunk.cyl(0, 0, trunk_h * 0.5, trunk_r, trunk_h, 7, rtop=trunk_r * 0.7)
    for i in range(3):
        a = i * 2.1
        trunk.cyl(math.cos(a) * 0.25, math.sin(a) * 0.25, trunk_h * 0.85,
                  trunk_r * 0.45, trunk_h * 0.35, 5,
                  rot=(math.radians(28) * math.sin(a), math.radians(28) * math.cos(a), 0))
    canopy = Part()
    for (dx, dy, dz, r, s) in blobs:
        canopy.sphere(dx * spread, dy * spread, trunk_h + dz * spread,
                      r * spread, 2, scale=(1.0, 1.0, s))
    t = trunk.obj(name + "_Trunk", "bark", col)
    c = canopy.obj(name + "_Canopy", "foliage", col)
    return [t, c]


def _instance(variant, name, collection, loc, rot, scale):
    out = []
    for src in variant:
        dup = C.linked_duplicate(src, name=name + src.name.split("_")[-1],
                                 collection=collection, loc=loc, rot=(0, 0, rot))
        dup.scale = (scale, scale, scale)
        out.append(dup)
    return out


# -----------------------------------------------------------------------------
def _trees_module_active():
    """True when trees.py will run, so we skip the legacy blob canopies."""
    only = CONFIG.get("only") or []
    if only:
        return "trees" in only
    return os.path.exists(os.path.join(_HERE, "trees.py"))


def build():
    collection = C.col("CITY_Vegetation")
    assets = C.ensure_collection("CITY_Assets", "CITY")
    R = rng("vegetation")
    plan = plan_city()
    detail = 1.0 if CONFIG["quality"] == "high" else 0.7

    variants = [
        _tree_variant("TreeA", 3.4, 0.20,
                      [(0, 0, 0.4, 1.9, 1.0), (0.9, 0.4, 0.1, 1.3, 0.9),
                       (-0.8, -0.5, 0.2, 1.4, 0.9), (0.2, -0.9, 0.6, 1.1, 0.85)],
                      1.0, assets),
        _tree_variant("TreeB", 4.6, 0.28,
                      [(0, 0, 0.6, 2.6, 0.85), (1.4, 0.6, 0.2, 1.8, 0.8),
                       (-1.3, -0.7, 0.3, 1.9, 0.8), (0.3, 1.4, 0.5, 1.6, 0.8),
                       (-0.4, -1.3, 0.7, 1.5, 0.8)],
                      1.0, assets),
        _tree_variant("TreeC", 2.6, 0.15,
                      [(0, 0, 0.3, 1.4, 1.0), (0.6, 0.3, 0.1, 0.9, 0.9)],
                      1.0, assets),
    ]

    n_street = n_park = 0

    # Trees are grown by trees.py (M19) with real branching; the blob variants
    # below are kept only as a fallback when that module is excluded.
    if "trees" not in (CONFIG.get("only") or []) and _trees_module_active():
        variants = []

    # ---- street trees in the pits cut by the sidewalk module
    for (x, y) in C.get_asset("tree_pits", []):
        if R.random() > 0.88 * detail:
            continue
        if not variants:
            break
        v = variants[R.choice([0, 0, 1, 2])]
        s = R.uniform(0.85, 1.15)
        _instance(v, "StreetTree_{:04d}_".format(n_street), collection,
                  (x, y, BASE_Z), R.uniform(0, math.tau), s)
        n_street += 1

    # ---- park trees
    for p in plan["parks"]:
        x0, y0, x1, y1 = p["x0"], p["x1"], p["y0"], p["y1"]
        for i in range(int((x1 - x0) * (y1 - y0) / 90.0 * detail)):
            x = R.uniform(x0 + 4.0, x1 - 4.0)
            y = R.uniform(y0 + 4.0, y1 - 4.0)
            if (x - p["cx"]) ** 2 + (y - p["cy"]) ** 2 < 36.0:
                continue
            if not variants:
                break
            v = variants[R.choice([0, 1, 1, 2])]
            _instance(v, "ParkTree_{:04d}_".format(n_park), collection,
                      (x, y, BASE_Z), R.uniform(0, math.tau), R.uniform(0.9, 1.35))
            n_park += 1

    # ---- hedges / bushes along building bases and in empty lots
    bm_bush = bmesh.new()
    n_bush = 0
    for b in plan["blocks"]:
        if b["district"] == "parkland":
            continue
        for i in range(R.randint(0, 4)):
            side = R.randint(0, 3)
            if side == 0:
                x, y = R.uniform(b["x0"] + 2, b["x1"] - 2), b["y0"] + 1.5
            elif side == 1:
                x, y = R.uniform(b["x0"] + 2, b["x1"] - 2), b["y1"] - 1.5
            elif side == 2:
                x, y = b["x0"] + 1.5, R.uniform(b["y0"] + 2, b["y1"] - 2)
            else:
                x, y = b["x1"] - 1.5, R.uniform(b["y0"] + 2, b["y1"] - 2)
            r = R.uniform(0.4, 0.9)
            bm2 = bmesh.new()
            try:
                bmesh.ops.create_icosphere(bm2, subdivisions=2, radius=1.0)
            except TypeError:
                bmesh.ops.create_icosphere(bm2, subdivisions=2, diameter=1.0)
            for v in bm2.verts:
                v.co.x = v.co.x * r + x
                v.co.y = v.co.y * r + y
                v.co.z = v.co.z * r * 0.8 + BASE_Z + r * 0.6
            me = bpy.data.meshes.new("_b")
            bm2.to_mesh(me)
            bm2.free()
            bm_bush.from_mesh(me)
            bpy.data.meshes.remove(me)
            n_bush += 1
    if len(bm_bush.faces):
        bmesh.ops.recalc_face_normals(bm_bush, faces=bm_bush.faces)
        me = bpy.data.meshes.new("Veg_Hedges_mesh")
        bm_bush.to_mesh(me)
        bm_bush.free()
        ob = bpy.data.objects.new("Veg_Hedges", me)
        C.link_object(ob, collection)
        ob.data.materials.append(C.M("foliage_dark"))

    # ---- weeds in the cracks along the curb line
    bm_weed = bmesh.new()
    for s in plan["roads_x"] + plan["roads_y"]:
        pass
    segs = C.get_asset("road_segments", [])
    for s in segs:
        L = s["b"] - s["a"]
        n = int(L / 3.0 * detail)
        for i in range(n):
            t = R.uniform(0.0, 1.0)
            along = s["a"] + L * t
            side = 1 if R.random() < 0.5 else -1
            off = side * (s["w"] * 0.5 - 0.35)
            if s["axis"] == "ns":
                x, y = s["c"] + off, along
            else:
                x, y = along, s["c"] + off
            h = R.uniform(0.10, 0.35)
            w = R.uniform(0.05, 0.14)
            for k in range(2):
                a = R.uniform(0, math.pi)
                ca, sa = math.cos(a), math.sin(a)
                vs = [bm_weed.verts.new((x - w * ca, y - w * sa, 0.02)),
                      bm_weed.verts.new((x + w * ca, y + w * sa, 0.02)),
                      bm_weed.verts.new((x + w * ca * 0.4, y + w * sa * 0.4, h)),
                      bm_weed.verts.new((x - w * ca * 0.4, y - w * sa * 0.4, h))]
                bm_weed.faces.new(vs)
    if len(bm_weed.faces):
        bmesh.ops.recalc_face_normals(bm_weed, faces=bm_weed.faces)
        me = bpy.data.meshes.new("Veg_Weeds_mesh")
        bm_weed.to_mesh(me)
        bm_weed.free()
        ob = bpy.data.objects.new("Veg_Weeds", me)
        C.link_object(ob, collection)
        ob.data.materials.append(C.M("foliage"))

    # ---- ivy patches on walls
    bm_ivy = bmesh.new()
    for b in C.get_asset("buildings", []):
        if not b or R.random() > 0.18:
            continue
        x0, y0, x1, y1 = b["rect"]
        h = b["height"]
        side = R.randint(0, 3)
        w = R.uniform(1.5, 4.0)
        hh = R.uniform(2.0, min(8.0, h - 1.0))
        zc = BASE_Z + R.uniform(1.0, max(1.2, h - hh - 0.5))
        if side == 0:
            cx, cy, ux, uy, nx, ny = (x0 + x1) * 0.5, y0, 1, 0, 0, -1
        elif side == 1:
            cx, cy, ux, uy, nx, ny = (x0 + x1) * 0.5, y1, 1, 0, 0, 1
        elif side == 2:
            cx, cy, ux, uy, nx, ny = x0, (y0 + y1) * 0.5, 0, 1, -1, 0
        else:
            cx, cy, ux, uy, nx, ny = x1, (y0 + y1) * 0.5, 0, 1, 1, 0
        ox, oy = nx * 0.02, ny * 0.02
        hw, hh2 = w * 0.5, hh * 0.5
        p = [(-hw, -hh2), (hw, -hh2), (hw, hh2), (-hw, hh2)]
        vs = [bm_ivy.verts.new((cx + ux * a + ox, cy + uy * a + oy, zc + b2))
              for (a, b2) in p]
        bm_ivy.faces.new(vs)
    if len(bm_ivy.faces):
        bmesh.ops.recalc_face_normals(bm_ivy, faces=bm_ivy.faces)
        me = bpy.data.meshes.new("Veg_Ivy_mesh")
        bm_ivy.to_mesh(me)
        bm_ivy.free()
        ob = bpy.data.objects.new("Veg_Ivy", me)
        C.link_object(ob, collection)
        ob.data.materials.append(C.M("foliage_dark"))

    # ---- moss patches + leaf litter on sidewalks
    bm_moss = bmesh.new()
    for i in range(int(220 * detail)):
        b = R.choice(plan["blocks"])
        x = R.uniform(b["x0"] + 1.0, b["x1"] - 1.0)
        y = R.uniform(b["y0"] + 1.0, b["y1"] - 1.0)
        s = R.uniform(0.15, 0.6)
        vs = [bm_moss.verts.new((x - s, y - s * 0.6, BASE_Z + 0.003)),
              bm_moss.verts.new((x + s, y - s * 0.6, BASE_Z + 0.003)),
              bm_moss.verts.new((x + s, y + s * 0.6, BASE_Z + 0.003)),
              bm_moss.verts.new((x - s, y + s * 0.6, BASE_Z + 0.003))]
        bm_moss.faces.new(vs)
    if len(bm_moss.faces):
        bmesh.ops.recalc_face_normals(bm_moss, faces=bm_moss.faces)
        me = bpy.data.meshes.new("Veg_Moss_mesh")
        bm_moss.to_mesh(me)
        bm_moss.free()
        ob = bpy.data.objects.new("Veg_Moss", me)
        C.link_object(ob, collection)
        ob.data.materials.append(C.M("foliage_dark"))

    # ---- stumps in the parks
    for p in plan["parks"]:
        for i in range(R.randint(1, 3)):
            x = R.uniform(p["x0"] + 5, p["x1"] - 5)
            y = R.uniform(p["y0"] + 5, p["y1"] - 5)
            add_cylinder("Veg_Stump", R.uniform(0.25, 0.45), R.uniform(0.4, 0.9),
                         loc=(x, y, BASE_Z + 0.3), mat="bark",
                         collection=collection, segments=9)

    print("  street trees: {}  park trees: {}  bushes: {}".format(
        n_street, n_park, n_bush))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="M12 VEGETATION")
    C.build_all_materials()
    import sidewalks
    sidewalks.build()
    build()
    C.report()