# =============================================================================
#  CITY BUILD  --  M18 : ANIMALS
#  Pigeons, gulls, crows, dogs, cats and rats.
#
#  Poly Haven has no CC0 animal scans and no permissively licensed photoscan
#  source could be found, so these are built procedurally: a tapered body,
#  head, beak/muzzle, legs and folded or spread wings, proportioned from real
#  measurements.  At street distance they read correctly, and they close the
#  "model village" gap that empty pavements leave.
#
#  standalone:  blender -b -P animals.py -- --seed 3
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

# real body lengths, metres
SPECIES = {
    "pigeon": dict(length=0.33, height=0.24, body="#6e7880", head="#56606a",
                   accent="#8d99a3", weight=46),
    "gull":   dict(length=0.44, height=0.33, body="#eceff2", head="#f4f6f8",
                   accent="#b8bfc6", weight=14),
    "crow":   dict(length=0.46, height=0.30, body="#1d1f23", head="#15171a",
                   accent="#2b2f35", weight=16),
    "sparrow":dict(length=0.16, height=0.12, body="#8a7154", head="#6d5942",
                   accent="#a8926f", weight=24),
    "dog":    dict(length=0.95, height=0.58, body="#8a6440", head="#7a5636",
                   accent="#4a3523", weight=10),
    "cat":    dict(length=0.52, height=0.30, body="#4a4742", head="#403d39",
                   accent="#2b2927", weight=8),
    "rat":    dict(length=0.24, height=0.10, body="#4a443e", head="#3d3832",
                   accent="#6b625a", weight=6),
}


class Shape:
    def __init__(self):
        self.bm = bmesh.new()
        self.tags = []

    def _tag(self, f0, mat):
        self.tags.append((f0, len(self.bm.faces), mat))

    def blob(self, c, r, squash=(1.0, 1.0, 1.0), seg=7, rings=5, mat=None):
        f0 = len(self.bm.faces)
        rows = []
        for ri in range(rings + 1):
            phi = math.pi * ri / rings
            row = []
            for si in range(seg):
                th = 2.0 * math.pi * si / seg
                row.append(self.bm.verts.new((
                    c[0] + r * math.sin(phi) * math.cos(th) * squash[0],
                    c[1] + r * math.sin(phi) * math.sin(th) * squash[1],
                    c[2] + r * math.cos(phi) * squash[2])))
            rows.append(row)
        for ri in range(rings):
            for si in range(seg):
                sj = (si + 1) % seg
                try:
                    self.bm.faces.new((rows[ri][si], rows[ri][sj],
                                       rows[ri + 1][sj], rows[ri + 1][si]))
                except ValueError:
                    pass
        self._tag(f0, mat)

    def cone(self, a, b, r0, r1=0.0, seg=5, mat=None):
        f0 = len(self.bm.faces)
        va, vb = Vector(a), Vector(b)
        axis = vb - va
        if axis.length < 1e-6:
            return
        rot = axis.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        L = axis.length
        bot, top = [], []
        for i in range(seg):
            ang = 2.0 * math.pi * i / seg
            bot.append(self.bm.verts.new(va + (rot @ Vector((r0 * math.cos(ang), r0 * math.sin(ang), 0.0)))))
            top.append(self.bm.verts.new(va + (rot @ Vector((r1 * math.cos(ang), r1 * math.sin(ang), L)))))
        for i in range(seg):
            j = (i + 1) % seg
            self.bm.faces.new((bot[i], bot[j], top[j], top[i]))
        try:
            self.bm.faces.new(list(reversed(bot)))
            self.bm.faces.new(top)
        except ValueError:
            pass
        self._tag(f0, mat)

    def wedge(self, c, size, rot=0.0, mat=None):
        f0 = len(self.bm.faces)
        hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
        ca, sa = math.cos(rot), math.sin(rot)
        pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        bot, top = [], []
        for (px, py) in pts:
            wx = c[0] + px * ca - py * sa
            wy = c[1] + px * sa + py * ca
            bot.append(self.bm.verts.new((wx, wy, c[2] - hz)))
            top.append(self.bm.verts.new((wx, wy, c[2] + hz)))
        self.bm.faces.new(list(reversed(bot)))
        self.bm.faces.new(top)
        for i in range(4):
            j = (i + 1) % 4
            self.bm.faces.new((bot[i], bot[j], top[j], top[i]))
        self._tag(f0, mat)

    def finish(self, name, collection, mats):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name + "_mesh")
        self.bm.to_mesh(me)
        self.bm.free()
        slots = {}
        for m in mats:
            if m not in slots:
                slots[m] = len(me.materials)
                me.materials.append(C.M(m))
        for (f0, f1, m) in self.tags:
            if m is None:
                continue
            idx = slots.get(m, 0)
            for fi in range(f0, min(f1, len(me.polygons))):
                me.polygons[fi].material_index = idx
        ob = bpy.data.objects.new(name, me)
        C.link_object(ob, collection)
        return ob


def _mats(spec):
    out = {}
    for label in ("body", "head", "accent"):
        hexv = spec[label]
        nm = "animal_{}_{}".format(label, hexv.lstrip("#"))
        if nm not in C.MATS:
            C.make_pbr(nm, base=hexv, roughness=0.70, bump=0.10,
                       grime=0.18, var_noise=2.0)
        out[label] = nm
    out["beak"] = "animal_beak"
    if "animal_beak" not in C.MATS:
        C.make_pbr("animal_beak", base="#c8a33c", roughness=0.45)
    return out


def build_bird(name, species, R, collection, flying=False):
    spec = SPECIES[species]
    M = _mats(spec)
    L, H = spec["length"], spec["height"]
    s = Shape()

    body_z = H * 0.52
    s.blob((0, 0, body_z), L * 0.30, squash=(1.0, 0.62, 0.66), mat=M["body"])
    # neck + head
    head_x = L * 0.30
    head_z = body_z + H * 0.26
    s.cone((L * 0.10, 0, body_z + H * 0.08), (head_x, 0, head_z),
           L * 0.09, L * 0.07, mat=M["head"])
    s.blob((head_x, 0, head_z), L * 0.115, squash=(1.0, 0.92, 0.95), mat=M["head"])
    s.cone((head_x + L * 0.07, 0, head_z), (head_x + L * 0.20, 0, head_z - H * 0.02),
           L * 0.035, 0.004, seg=4, mat=M["beak"])
    # tail
    s.wedge((-L * 0.38, 0, body_z + H * 0.02), (L * 0.30, L * 0.16, H * 0.035),
            mat=M["accent"])

    if flying:
        for sgn in (-1, 1):
            s.wedge((0, sgn * L * 0.34, body_z + H * 0.12),
                    (L * 0.34, L * 0.56, H * 0.03), rot=sgn * 0.18, mat=M["accent"])
    else:
        for sgn in (-1, 1):
            s.wedge((-L * 0.04, sgn * L * 0.17, body_z),
                    (L * 0.40, L * 0.10, H * 0.16), mat=M["accent"])
        for sgn in (-1, 1):
            s.cone((sgn * L * 0.07, sgn * L * 0.05, body_z - L * 0.17),
                   (sgn * L * 0.07, sgn * L * 0.05, 0.0), L * 0.016, L * 0.012,
                   seg=4, mat=M["beak"])
    return s.finish(name, collection, list(set(M.values())))


def build_quadruped(name, species, R, collection):
    spec = SPECIES[species]
    M = _mats(spec)
    L, H = spec["length"], spec["height"]
    s = Shape()

    back_z = H * 0.68
    s.blob((0, 0, back_z), L * 0.26, squash=(1.0, 0.56, 0.52), mat=M["body"])
    s.blob((L * 0.22, 0, back_z + H * 0.04), L * 0.17,
           squash=(0.9, 0.62, 0.58), mat=M["body"])
    # neck + head
    head_x, head_z = L * 0.44, back_z + H * 0.20
    s.cone((L * 0.28, 0, back_z + H * 0.06), (head_x, 0, head_z),
           L * 0.10, L * 0.08, mat=M["head"])
    s.blob((head_x, 0, head_z), L * 0.11, squash=(1.05, 0.85, 0.85), mat=M["head"])
    s.cone((head_x + L * 0.06, 0, head_z - H * 0.03),
           (head_x + L * 0.16, 0, head_z - H * 0.06),
           L * 0.05, L * 0.035, seg=5, mat=M["head"])
    # ears
    for sgn in (-1, 1):
        s.cone((head_x - L * 0.02, sgn * L * 0.06, head_z + L * 0.06),
               (head_x - L * 0.03, sgn * L * 0.09, head_z + L * 0.16),
               L * 0.035, 0.004, seg=4, mat=M["accent"])
    # legs
    for fx in (L * 0.26, -L * 0.22):
        for sgn in (-1, 1):
            hipz = back_z - L * 0.10
            s.cone((fx, sgn * L * 0.12, hipz), (fx, sgn * L * 0.13, 0.0),
                   L * 0.045, L * 0.030, seg=4, mat=M["body"])
    # tail
    s.cone((-L * 0.30, 0, back_z + H * 0.02),
           (-L * 0.46, 0, back_z + H * 0.18), L * 0.035, L * 0.012,
           seg=4, mat=M["accent"])
    return s.finish(name, collection, list(set(M.values())))


def _dup(src, name, collection, loc, rot, scale=1.0):
    ob = bpy.data.objects.new(name, src.data)
    ob.location = loc
    ob.rotation_euler = (0.0, 0.0, rot)
    ob.scale = (scale, scale, scale)
    C.link_object(ob, collection)
    return ob


def build():
    R = rng("animals")
    plan = plan_city()
    half = plan["half"]
    col = C.col("CITY_Animals")
    src_col = C.col("CITY_Animals_src")
    density = CONFIG.get("density", 0.8)

    sources = {}
    for sp in ("pigeon", "gull", "crow", "sparrow"):
        sources[sp] = build_bird("SRC_" + sp, sp, R, src_col, flying=False)
        sources[sp + "_fly"] = build_bird("SRC_" + sp + "_fly", sp, R, src_col, flying=True)
    for sp in ("dog", "cat", "rat"):
        sources[sp] = build_quadruped("SRC_" + sp, sp, R, src_col)
    for ob in sources.values():
        ob.hide_render = True
        ob.hide_viewport = True

    ground_weights = [(k, SPECIES[k]["weight"]) for k in
                      ("pigeon", "gull", "crow", "sparrow", "dog", "cat", "rat")]
    total_w = sum(w for _, w in ground_weights)

    def pick_ground():
        t = R.uniform(0, total_w)
        acc = 0
        for k, w in ground_weights:
            acc += w
            if t <= acc:
                return k
        return "pigeon"

    n = 0

    # --- flocks on pavement and plazas -----------------------------------
    for _ in range(int(26 * density)):
        fx, fy = R.uniform(-half, half), R.uniform(-half, half)
        for _ in range(R.randint(3, 11)):
            sp = pick_ground()
            if sp in ("dog", "cat", "rat"):
                sp = "pigeon"
            x = fx + R.gauss(0, 1.8)
            y = fy + R.gauss(0, 1.8)
            if abs(x) > half or abs(y) > half:
                continue
            _dup(sources[sp], "Animal_{:04d}".format(n), col,
                 (x, y, BASE_Z), R.uniform(0, math.tau),
                 R.uniform(0.9, 1.12))
            n += 1

    # --- birds perched on roof edges and wires ---------------------------
    perches = [o for o in bpy.data.objects
               if o.name.startswith(("RoofDeck", "Parapet", "StreetLight", "Pole"))]
    R.shuffle(perches)
    for ob in perches[:int(120 * density)]:
        if R.random() > 0.5:
            continue
        for _ in range(R.randint(1, 4)):
            sp = R.choice(["pigeon", "crow", "gull", "sparrow"])
            _dup(sources[sp], "Animal_perch_{:04d}".format(n), col,
                 (ob.location.x + R.uniform(-1.6, 1.6),
                  ob.location.y + R.uniform(-1.6, 1.6),
                  ob.location.z + 0.08),
                 R.uniform(0, math.tau), R.uniform(0.9, 1.1))
            n += 1

    # --- birds in flight --------------------------------------------------
    for _ in range(int(40 * density)):
        sp = R.choice(["pigeon_fly", "gull_fly", "crow_fly"])
        _dup(sources[sp], "Animal_fly_{:04d}".format(n), col,
             (R.uniform(-half, half), R.uniform(-half, half),
              R.uniform(9.0, 42.0)),
             R.uniform(0, math.tau), R.uniform(0.95, 1.2))
        n += 1

    # --- strays at street level -------------------------------------------
    for _ in range(int(14 * density)):
        sp = R.choice(["dog", "cat", "cat", "rat"])
        _dup(sources[sp], "Animal_stray_{:04d}".format(n), col,
             (R.uniform(-half, half), R.uniform(-half, half), BASE_Z),
             R.uniform(0, math.tau), R.uniform(0.9, 1.15))
        n += 1

    print("  animals: {} from {} species models".format(n, len(sources)))
    return n


if __name__ == "__main__":
    C.bootstrap(banner="M18 ANIMALS")
    C.build_all_materials()
    build()
    C.report()
