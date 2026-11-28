# =============================================================================
#  CITY BUILD  --  M13 : SIGNAGE, LITTER, GRAFFITI, POSTERS, PUDDLES
#  standalone:  blender -b -P story.py -- --quality preview
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
ROAD_Z = 0.02
# Puddle surface sits just above the road paint (roads.Z_PAINT = 0.030) so water
# covers lane markings and crosswalks instead of the paint floating on top.
PUDDLE_Z = 0.034


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


def _extra_materials():
    C.make_pbr("graffiti_a", base="#c8342f", roughness=0.85, bump=0.10,
               bump_scale=20, var_noise=9, grime=0.3)
    C.make_pbr("graffiti_b", base="#2f6fc8", roughness=0.85, bump=0.10,
               bump_scale=20, var_noise=9, grime=0.3)
    C.make_pbr("graffiti_c", base="#d8c33a", roughness=0.85, bump=0.10,
               bump_scale=20, var_noise=9, grime=0.3)
    C.make_pbr("poster_paper", base="#d6cfbd", roughness=0.95, bump=0.12,
               bump_scale=22, var_noise=11, grime=0.3)


def _vquad(bm, cx, cy, cz, ux, uy, nx, ny, w, h, out=0.0):
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


# -----------------------------------------------------------------------------
def build():
    _extra_materials()
    collection = C.col("CITY_Story")
    R = rng("story")
    plan = plan_city()
    detail = 1.0 if CONFIG["quality"] == "high" else 0.7

    # ---------------- street name signs + traffic signs at intersections
    n_street_sign = 0
    n_traffic_sign = 0
    for it in plan["intersections"]:
        if R.random() > 0.55:
            continue
        cx, cy = it["x"], it["y"]
        wns, wew = it["w"], it["h"]
        px = cx + wns * 0.5 + 0.55
        py = cy + wew * 0.5 + 0.55
        p = Part()
        p.cyl(0, 0, 2.1, 0.05, 4.0, 6)
        p.obj("StreetSignPole_{:04d}".format(n_street_sign), "metal_galv",
              collection, loc=(px, py, BASE_Z))
        p2 = Part()
        p2.box(0.55, 0, 3.85, 1.10, 0.04, 0.22)
        p2.box(0.0, 0.55, 3.62, 0.04, 1.10, 0.22)
        p2.obj("StreetSignBlade_{:04d}".format(n_street_sign), "paint_green",
               collection, loc=(px, py, BASE_Z))
        n_street_sign += 1

        if R.random() < 0.5:
            kind = R.choice(["stop", "yield", "speed", "oneway", "noparking"])
            p3 = Part()
            p3.cyl(0.9, 0, 1.5, 0.04, 2.8, 6)
            if kind == "stop":
                p3.box(0.9, 0, 2.55, 0.75, 0.05, 0.75)
            elif kind == "yield":
                p3.box(0.9, 0, 2.55, 0.70, 0.05, 0.70)
            elif kind == "speed":
                p3.box(0.9, 0, 2.55, 0.55, 0.05, 0.75)
            elif kind == "oneway":
                p3.box(0.9, 0, 2.55, 0.90, 0.05, 0.30)
            else:
                p3.box(0.9, 0, 2.55, 0.55, 0.05, 0.70)
            mat = {"stop": "paint_red", "yield": "paint_red",
                   "speed": "paint_white", "oneway": "paint_white",
                   "noparking": "paint_red"}[kind]
            p3.obj("TrafficSign_{:04d}".format(n_traffic_sign), mat,
                   collection, loc=(px, py, BASE_Z))
            n_traffic_sign += 1

    # ---------------- projecting blade signs + billboards on buildings
    n_blade = n_billboard = 0
    neon_mats = ["neon_pink", "neon_blue", "neon_red", "neon_green", "lamp_warm"]
    for b in C.get_asset("buildings", []):
        if not b:
            continue
        x0, y0, x1, y1 = b["rect"]
        h = b["height"]
        if R.random() < 0.30 and h > 6.0:
            side = R.randint(0, 3)
            if side == 0:
                px, py, nx, ny = (x0 + x1) * 0.5, y0, 0, -1
            elif side == 1:
                px, py, nx, ny = (x0 + x1) * 0.5, y1, 0, 1
            elif side == 2:
                px, py, nx, ny = x0, (y0 + y1) * 0.5, -1, 0
            else:
                px, py, nx, ny = x1, (y0 + y1) * 0.5, 1, 0
            z = BASE_Z + R.uniform(3.2, max(3.4, min(h - 1.5, 9.0)))
            p = Part()
            p.box(nx * 0.55, ny * 0.55, 0.0, 1.10, 0.08, 0.90)
            p.obj("BladeSign_{:04d}".format(n_blade),
                  R.choice(neon_mats), collection, loc=(px, py, z))
            n_blade += 1

        if R.random() < 0.10 and h > 12.0 and (x1 - x0) > 10.0:
            p = Part()
            p.box(0, 0, 0, 6.0, 0.25, 3.0)
            p.box(0, 0, -1.7, 0.3, 0.3, 1.4)
            p.obj("Billboard_{:04d}".format(n_billboard), "metal_dark",
                  collection,
                  loc=((x0 + x1) * 0.5, y0 - 0.4, BASE_Z + h + 2.2))
            p2 = Part()
            p2.box(0, -0.16, 0, 5.7, 0.04, 2.7)
            p2.obj("BillboardFace_{:04d}".format(n_billboard),
                   R.choice(["paint_white", "car_paint_red", "car_paint_blue"]),
                   collection,
                   loc=((x0 + x1) * 0.5, y0 - 0.4, BASE_Z + h + 2.2))
            n_billboard += 1

    # ---------------- graffiti + posters on walls
    bm_graffiti = [bmesh.new() for _ in range(3)]
    bm_poster = bmesh.new()
    n_graffiti = n_poster = 0
    for b in C.get_asset("buildings", []):
        if not b:
            continue
        x0, y0, x1, y1 = b["rect"]
        if R.random() > 0.35:
            continue
        side = R.randint(0, 3)
        if side == 0:
            cx, cy, ux, uy, nx, ny, ln = (x0 + x1) * 0.5, y0, 1, 0, 0, -1, x1 - x0
        elif side == 1:
            cx, cy, ux, uy, nx, ny, ln = (x0 + x1) * 0.5, y1, 1, 0, 0, 1, x1 - x0
        elif side == 2:
            cx, cy, ux, uy, nx, ny, ln = x0, (y0 + y1) * 0.5, 0, 1, -1, 0, y1 - y0
        else:
            cx, cy, ux, uy, nx, ny, ln = x1, (y0 + y1) * 0.5, 0, 1, 1, 0, y1 - y0

        for k in range(R.randint(1, 3)):
            s = R.uniform(-ln * 0.35, ln * 0.35)
            z = BASE_Z + R.uniform(0.6, 2.6)
            w = R.uniform(1.2, 3.4)
            h = R.uniform(0.7, 1.8)
            _vquad(bm_graffiti[R.randint(0, 2)],
                   cx + ux * s, cy + uy * s, z, ux, uy, nx, ny, w, h, out=0.012)
            n_graffiti += 1

        if R.random() < 0.5:
            s = R.uniform(-ln * 0.4, ln * 0.4)
            z = BASE_Z + R.uniform(1.2, 2.8)
            _vquad(bm_poster, cx + ux * s, cy + uy * s, z,
                   ux, uy, nx, ny, R.uniform(0.5, 1.1), R.uniform(0.7, 1.3),
                   out=0.014)
            n_poster += 1

    for i, bm in enumerate(bm_graffiti):
        _mesh("Story_Graffiti_{}".format(i), bm,
              ["graffiti_a", "graffiti_b", "graffiti_c"][i], collection)
    _mesh("Story_Posters", bm_poster, "poster_paper", collection)

    # ---------------- litter
    bm_paper = bmesh.new()
    bm_plastic = bmesh.new()
    bm_card = bmesh.new()
    for i in range(int(420 * detail)):
        b = R.choice(plan["blocks"])
        x = R.uniform(b["x0"] + 0.6, b["x1"] - 0.6)
        y = R.uniform(b["y0"] + 0.6, b["y1"] - 0.6)
        s = R.uniform(0.08, 0.26)
        z = BASE_Z + 0.004
        a = R.uniform(0, math.tau)
        ca, sa = math.cos(a), math.sin(a)
        vs = [bm_paper.verts.new((x - s * ca, y - s * sa, z)),
              bm_paper.verts.new((x + s * ca, y + s * sa, z)),
              bm_paper.verts.new((x + s * ca * 0.7 - s * sa * 0.7,
                                  y + s * sa * 0.7 + s * ca * 0.7, z)),
              bm_paper.verts.new((x - s * ca * 0.7 - s * sa * 0.7,
                                  y - s * sa * 0.7 + s * ca * 0.7, z))]
        bm_paper.faces.new(vs)
        if R.random() < 0.4:
            bm2 = bm_plastic
            vs2 = [bm2.verts.new((x + 0.1 - s * 0.4, y - s * 0.4, z + 0.03)),
                   bm2.verts.new((x + 0.1 + s * 0.4, y - s * 0.4, z + 0.03)),
                   bm2.verts.new((x + 0.1 + s * 0.4, y + s * 0.4, z + 0.03)),
                   bm2.verts.new((x + 0.1 - s * 0.4, y + s * 0.4, z + 0.03))]
            bm2.faces.new(vs2)
        if R.random() < 0.2:
            vs3 = [bm_card.verts.new((x - 0.3, y - 0.2, z + 0.05)),
                   bm_card.verts.new((x + 0.3, y - 0.2, z + 0.05)),
                   bm_card.verts.new((x + 0.3, y + 0.2, z + 0.05)),
                   bm_card.verts.new((x - 0.3, y + 0.2, z + 0.05))]
            bm_card.faces.new(vs3)

    _mesh("Story_Litter_Paper", bm_paper, "paper", collection)
    _mesh("Story_Litter_Plastic", bm_plastic, "plastic", collection)
    _mesh("Story_Litter_Cardboard", bm_card, "cardboard", collection)

    # ---------------- puddles on the road
    # Each puddle is a triangle fan with a centre vertex. The per-vertex
    # "puddle_edge" value (0 centre, 1 rim) drives the puddle material's
    # roughness/colour ramp, so the middle mirrors and the rim looks damp.
    bm_puddle = bmesh.new()
    edge_layer = bm_puddle.verts.layers.float.new(C.PUDDLE_ATTR)
    segs = C.get_asset("road_segments", [])
    for s in segs:
        L = s["b"] - s["a"]
        for i in range(int(L / 22.0 * detail)):
            along = s["a"] + R.uniform(1.0, max(1.2, L - 1.0))
            across = s["c"] + R.uniform(-s["w"] * 0.4, s["w"] * 0.4)
            if s["axis"] == "ns":
                x, y = across, along
            else:
                x, y = along, across
            r = R.uniform(0.4, 1.5)
            seg = 16
            zc = PUDDLE_Z
            hub = bm_puddle.verts.new((x, y, zc))
            hub[edge_layer] = 0.0
            # radius noise is smoothed over neighbours so the outline is a
            # soft blob, not a spiky star
            raw = [R.random() for _ in range(seg)]
            ring = []
            for k in range(seg):
                a = math.tau * k / seg
                sm = (raw[k - 1] + 2.0 * raw[k] + raw[(k + 1) % seg]) * 0.25
                rr = r * (0.78 + sm * 0.44)
                v = bm_puddle.verts.new((x + rr * math.cos(a) * 1.4,
                                         y + rr * math.sin(a), zc))
                v[edge_layer] = 1.0
                ring.append(v)
            for k in range(seg):
                bm_puddle.faces.new((hub, ring[k], ring[(k + 1) % seg]))
    if len(bm_puddle.faces):
        _mesh("Story_Puddles", bm_puddle, "puddle", collection)
    else:
        bm_puddle.free()

    print("  street signs: {}  traffic signs: {}  blades: {}  billboards: {}  graffiti: {}  posters: {}".format(
        n_street_sign, n_traffic_sign, n_blade, n_billboard, n_graffiti, n_poster))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="M13 STORY")
    C.build_all_materials()
    import buildings_types
    buildings_types.build()
    build()
    C.report()