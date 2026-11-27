# =============================================================================
#  CITY BUILD  --  M19 : TREES
#  Real branching trees, replacing the sphere-on-a-stick canopies.
#
#  Poly Haven's photoscanned trees are ~500 MB of geometry each, which a city
#  of hundreds cannot carry, so these are grown procedurally from botanical
#  rules rather than modelled as blobs:
#
#    * da Vinci's rule - parent radius^2 = sum of child radii^2, so limb
#      thickness tapers the way real wood does
#    * phyllotaxis - successive branches rotate 137.5 degrees around the
#      parent, which is what stops a tree looking like a candelabra
#    * gravitropism - young shoots bend back toward vertical, so outer twigs
#      lift instead of drooping in straight lines
#    * apical dominance varies by species: a poplar keeps one leader, an oak
#      forks early and spreads
#
#  Leaves are crossed quad clusters at the twig tips, not spheres, so the
#  canopy breaks up against the sky instead of reading as a solid ball.
#
#  standalone:  blender -b -P trees.py -- --seed 5
# =============================================================================
import bpy
import bmesh
import math
import os
import sys
from mathutils import Euler, Matrix, Quaternion, Vector

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, U, rng, plan_city

BASE_Z = 0.15
GOLDEN = math.radians(137.5)

# species -> growth parameters
#   height          overall metres
#   clear           bare trunk before first branch (street trees are pruned high)
#   levels          recursion depth
#   splits          children per node
#   angle           divergence from parent, degrees
#   len_decay       child length / parent length
#   taper           trunk radius / height
#   gravity         upward correction applied per level (0 = none)
#   leader          apical dominance 0..1 (1 = single straight leader)
SPECIES = {
    "street_plane": dict(height=(7.5, 11.0), clear=0.42, levels=4, splits=(2, 3),
                         angle=(32, 46), len_decay=(0.68, 0.78), taper=0.030,
                         gravity=0.35, leader=0.55, leaf=("foliage", 0.95)),
    "street_maple": dict(height=(6.5, 9.5), clear=0.38, levels=4, splits=(2, 3),
                         angle=(30, 44), len_decay=(0.66, 0.76), taper=0.032,
                         gravity=0.30, leader=0.45, leaf=("foliage", 1.05)),
    "park_oak":     dict(height=(9.0, 14.0), clear=0.26, levels=5, splits=(2, 3),
                         angle=(38, 58), len_decay=(0.64, 0.74), taper=0.042,
                         gravity=0.22, leader=0.18, leaf=("foliage", 1.25)),
    "poplar":       dict(height=(11.0, 16.0), clear=0.30, levels=4, splits=(2, 2),
                         angle=(16, 26), len_decay=(0.70, 0.80), taper=0.022,
                         gravity=0.55, leader=0.90, leaf=("foliage", 0.70)),
    "conifer":      dict(height=(8.0, 15.0), clear=0.12, levels=3, splits=(4, 5),
                         angle=(62, 78), len_decay=(0.58, 0.68), taper=0.034,
                         gravity=0.05, leader=0.95, leaf=("foliage_dark", 0.80)),
    "sapling":      dict(height=(2.6, 4.2), clear=0.30, levels=3, splits=(2, 3),
                         angle=(28, 42), len_decay=(0.64, 0.74), taper=0.024,
                         gravity=0.40, leader=0.60, leaf=("foliage", 0.60)),
    "bare":         dict(height=(6.0, 10.0), clear=0.34, levels=5, splits=(2, 3),
                         angle=(34, 52), len_decay=(0.66, 0.76), taper=0.030,
                         gravity=0.28, leader=0.35, leaf=None),
}


class Growth:
    """Accumulates branch geometry into one bmesh."""

    def __init__(self):
        self.bm = bmesh.new()
        self.wood_faces = 0
        self.leaf_quads = []       # (origin, direction, size)

    # -- a tapered limb between two points ------------------------------
    def limb(self, start, end, r0, r1, seg=5):
        axis = end - start
        length = axis.length
        if length < 1e-4 or r0 < 1e-4:
            return
        rot = axis.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        ring0, ring1 = [], []
        for i in range(seg):
            a = 2.0 * math.pi * i / seg
            c, s = math.cos(a), math.sin(a)
            ring0.append(self.bm.verts.new(start + (rot @ Vector((r0 * c, r0 * s, 0.0)))))
            ring1.append(self.bm.verts.new(start + (rot @ Vector((r1 * c, r1 * s, length)))))
        for i in range(seg):
            j = (i + 1) % seg
            self.bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
            self.wood_faces += 1
        self.bm.faces.new(list(reversed(ring0)))
        self.wood_faces += 1

    def root_flare(self, origin, radius, count=5, R=None):
        """Buttress roots: a trunk that meets the ground as a cylinder reads fake."""
        for i in range(count):
            a = 2.0 * math.pi * i / count + (R.uniform(-0.3, 0.3) if R else 0.0)
            out = Vector((math.cos(a), math.sin(a), 0.0)) * radius * 1.9
            self.limb(origin + out * 0.95 + Vector((0, 0, 0.02)),
                      origin + Vector((0, 0, radius * 3.4)),
                      radius * 0.42, radius * 0.16, seg=4)


def _grow(g, origin, direction, length, radius, level, spec, R, leaf_scale):
    """Recursively grow one branch and its children."""
    end = origin + direction * length
    child_r = radius * math.sqrt(1.0 / max(1, _n_children(spec, level, R)))
    g.limb(origin, end, radius, max(child_r * 0.92, radius * 0.30))

    if level <= 0:
        if spec["leaf"] is not None:
            g.leaf_quads.append((end, direction.copy(),
                                 length * 0.95 * leaf_scale))
        return

    n = _n_children(spec, level, R)
    base_angle = R.uniform(*spec["angle"])
    phase = R.uniform(0.0, math.tau)

    for i in range(n):
        # phyllotaxis keeps successive children out of plane
        around = phase + GOLDEN * i + R.uniform(-0.25, 0.25)
        ang = math.radians(base_angle * R.uniform(0.80, 1.20))

        # the straightest child inherits the leader
        is_leader = (i == 0 and R.random() < spec["leader"])
        if is_leader:
            ang *= 0.25

        perp = direction.orthogonal().normalized()
        axis = Quaternion(direction, around) @ perp
        new_dir = (Quaternion(axis, ang) @ direction).normalized()

        # gravitropism: pull shoots back toward vertical as they thin out
        lift = spec["gravity"] * (1.0 - level / float(spec["levels"]))
        new_dir = (new_dir * (1.0 - lift) + Vector((0, 0, 1)) * lift).normalized()

        decay = R.uniform(*spec["len_decay"])
        child_len = length * decay * (1.12 if is_leader else 1.0)
        # branch point is spread along the parent, not all from the tip
        t = 1.0 if is_leader else R.uniform(0.62, 1.0)
        start = origin + direction * (length * t)

        _grow(g, start, new_dir, child_len, child_r, level - 1, spec, R, leaf_scale)


def _n_children(spec, level, R):
    lo, hi = spec["splits"]
    return R.randint(lo, hi) if hi > lo else lo


def _leaf_mesh(g, mat_name, col, name):
    """Crossed quads at every twig tip - cheap, and breaks the silhouette."""
    if not g.leaf_quads:
        return None
    bm = bmesh.new()
    for (pos, direction, size) in g.leaf_quads:
        rot = direction.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        for k in range(3):
            a = math.pi * k / 3.0
            ca, sa = math.cos(a), math.sin(a)
            w, h = size * 0.95, size * 1.25
            pts = [Vector((-w * ca, -w * sa, -h * 0.25)),
                   Vector(( w * ca,  w * sa, -h * 0.25)),
                   Vector(( w * ca,  w * sa,  h * 0.85)),
                   Vector((-w * ca, -w * sa,  h * 0.85))]
            vs = [bm.verts.new(pos + (rot @ p)) for p in pts]
            bm.faces.new(vs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_leaf_mesh")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(C.M(mat_name))
    ob = bpy.data.objects.new(name + "_Leaves", me)
    C.link_object(ob, col)
    return ob


def build_tree(name, species, R, col):
    spec = SPECIES[species]
    height = R.uniform(*spec["height"])
    radius = height * spec["taper"] * R.uniform(0.88, 1.12)
    clear = height * spec["clear"]

    g = Growth()
    origin = Vector((0.0, 0.0, 0.0))
    g.root_flare(origin, radius, R=R)

    # bare trunk to the first fork, with a slight natural lean
    lean = Vector((R.gauss(0, 0.05), R.gauss(0, 0.05), 1.0)).normalized()
    trunk_top = origin + lean * clear
    g.limb(origin, trunk_top, radius * 1.15, radius * 0.86, seg=7)

    leaf_name, leaf_scale = (spec["leaf"] if spec["leaf"] else ("foliage", 1.0))
    _grow(g, trunk_top, lean, height - clear, radius * 0.86,
          spec["levels"], spec, R, leaf_scale)

    bmesh.ops.recalc_face_normals(g.bm, faces=g.bm.faces)
    me = bpy.data.meshes.new(name + "_mesh")
    g.bm.to_mesh(me)
    g.bm.free()
    me.materials.append(C.M("bark"))
    wood = bpy.data.objects.new(name, me)
    C.link_object(wood, col)

    parts = [wood]
    if spec["leaf"] is not None:
        leaves = _leaf_mesh(g, leaf_name, col, name)
        if leaves:
            parts.append(leaves)
    return parts


# -----------------------------------------------------------------------------
def _variants(R, src_col):
    """Grow a palette of trees once; the city instances these."""
    plan = [("street_plane", 3), ("street_maple", 3), ("park_oak", 3),
            ("poplar", 2), ("conifer", 2), ("sapling", 2), ("bare", 2)]
    out = []
    for species, n in plan:
        for i in range(n):
            parts = build_tree("Tree_{}_{}".format(species, i), species, R, src_col)
            for p in parts:
                p.hide_render = True
                p.hide_viewport = True
            out.append((species, parts))
    return out


def _instance(parts, name, col, loc, rot, scale):
    for src in parts:
        ob = bpy.data.objects.new(name + "_" + src.name.split("_")[-1], src.data)
        ob.location = loc
        ob.rotation_euler = (0.0, 0.0, rot)
        ob.scale = (scale, scale, scale)
        C.link_object(ob, col)


def build():
    R = rng("trees")
    plan = plan_city()
    col = C.col("CITY_Trees")
    src_col = C.col("CITY_Trees_src")
    half = plan["half"]
    density = CONFIG.get("density", 0.8)

    variants = _variants(R, src_col)
    by_species = {}
    for species, parts in variants:
        by_species.setdefault(species, []).append(parts)

    def pick(*names):
        pool = []
        for nm in names:
            pool.extend(by_species.get(nm, []))
        return R.choice(pool) if pool else None

    n = 0
    spacing = 11.0          # real street-tree spacing
    sw = U["sidewalk"]

    # --- street trees along block frontages ------------------------------
    for blk in plan["blocks"]:
        cx, cy, bw, bh = blk["cx"], blk["cy"], blk["w"], blk["h"]
        district = blk.get("district", "midtown")
        if district == "industrial" and R.random() < 0.55:
            continue
        for (along, cross, horiz) in ((bw, bh, True), (bh, bw, False)):
            count = max(0, int(along / spacing))
            for i in range(count):
                if R.random() > 0.78 * density:
                    continue
                t = (i + 0.5) / max(1, count) - 0.5
                for sgn in (-1, 1):
                    if R.random() > 0.72:
                        continue
                    if horiz:
                        x = cx + along * t
                        y = cy + sgn * (cross * 0.5 + sw * 0.42)
                    else:
                        y = cy + along * t
                        x = cx + sgn * (cross * 0.5 + sw * 0.42)
                    if abs(x) > half or abs(y) > half:
                        continue
                    parts = pick("street_plane", "street_maple") \
                        if R.random() < 0.88 else pick("sapling", "bare")
                    if not parts:
                        continue
                    _instance(parts, "Tree_{:04d}".format(n), col,
                              (x + R.gauss(0, 0.20), y + R.gauss(0, 0.20), BASE_Z),
                              R.uniform(0, math.tau), R.uniform(0.86, 1.16))
                    n += 1

    # --- parks: mixed stands, bigger canopies ----------------------------
    for park in plan.get("parks", []):
        px, py = park.get("cx", 0.0), park.get("cy", 0.0)
        pw, ph = park.get("w", 40.0), park.get("h", 40.0)
        for _ in range(int(max(6, (pw * ph) / 90.0) * density)):
            parts = pick("park_oak", "street_plane", "conifer", "poplar")
            if not parts:
                continue
            _instance(parts, "Tree_park_{:04d}".format(n), col,
                      (px + R.uniform(-pw * 0.45, pw * 0.45),
                       py + R.uniform(-ph * 0.45, ph * 0.45), BASE_Z),
                      R.uniform(0, math.tau), R.uniform(0.90, 1.35))
            n += 1

    print("  trees: {} instances from {} grown variants".format(n, len(variants)))
    return n


if __name__ == "__main__":
    C.bootstrap(banner="M19 TREES")
    C.build_all_materials()
    build()
    C.report()
