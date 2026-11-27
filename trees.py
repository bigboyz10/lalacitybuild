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


# --- T-009: canopy variety ---------------------------------------------------
#
# Critique 7 was that street trees are evenly spaced and the same three
# silhouettes repeat. Four things fix that, and they are separable:
#
#   1. species mix varies by district - a civic boulevard is planted
#      differently from an industrial back street
#   2. health varies - councils plant, then neglect; a real street has
#      thriving trees next to stressed ones, dead stumps and empty pits
#   3. foliage colour varies per instance, so even two copies of the same
#      grown silhouette do not read as clones
#   4. spacing wanders - planting follows driveways, hydrants and crossings,
#      so gaps are irregular rather than metronomic

# district -> (species, weight). Weights are relative.
DISTRICT_MIX = {
    "downtown":    [("street_plane", 5), ("street_maple", 3), ("poplar", 1)],
    "midtown":     [("street_plane", 4), ("street_maple", 4), ("park_oak", 1),
                    ("poplar", 1)],
    "residential": [("street_maple", 5), ("park_oak", 3), ("street_plane", 2),
                    ("conifer", 1)],
    "waterfront":  [("street_plane", 3), ("poplar", 3), ("conifer", 2)],
    "industrial":  [("poplar", 3), ("street_maple", 2), ("bare", 2),
                    ("sapling", 2)],
}

# health state -> (weight, canopy scale, foliage tint, trunk-only?)
#   tint multiplies the base foliage colour, so a stressed tree yellows and a
#   dying one browns without needing separate grown geometry.
HEALTH = [
    ("thriving", 46, 1.08, (1.00, 1.06, 0.94), False),
    ("healthy",  28, 1.00, (1.00, 1.00, 1.00), False),
    ("stressed", 13, 0.86, (1.18, 1.02, 0.62), False),
    ("dying",     7, 0.72, (1.22, 0.88, 0.48), False),
    ("dead",      6, 0.80, (0.70, 0.62, 0.52), True),
]

# fraction of pits that hold no tree at all, by district: councils remove
# trees and do not always replant.
EMPTY_PIT = {"downtown": 0.07, "midtown": 0.09, "residential": 0.06,
             "waterfront": 0.12, "industrial": 0.26}

# of the empty pits, how many keep a cut stump rather than bare soil
STUMP_SHARE = 0.45

_TINT_MATS = {}


def _weighted(pairs, R):
    total = sum(w for _, w in pairs)
    t = R.uniform(0.0, total)
    acc = 0.0
    for item, w in pairs:
        acc += w
        if t <= acc:
            return item
    return pairs[0][0]


def _health(R):
    pick = _weighted([(h[0], h[1]) for h in HEALTH], R)
    for row in HEALTH:
        if row[0] == pick:
            return row
    return HEALTH[1]


def _tinted_foliage(base_name, tint, R):
    """A per-instance foliage material. Mesh data stays shared; only the
    material slot is overridden on the object, so this costs no geometry."""
    # Quantise the jitter: without this every tree gets its own material and
    # the palette balloons to one entry per instance, which kills batching for
    # no visible gain. A 0.05 grid still yields dozens of distinguishable
    # greens while keeping the material count in the tens.
    def q(v):
        return round(round(v / 0.05) * 0.05, 3)
    jitter = (q(tint[0] * R.uniform(0.93, 1.07)),
              q(tint[1] * R.uniform(0.93, 1.07)),
              q(tint[2] * R.uniform(0.93, 1.07)))
    key = (base_name, jitter)
    if key in _TINT_MATS:
        return _TINT_MATS[key]
    src = C.PALETTE.get(base_name, dict(base="#3d5929", roughness=0.90))
    hexv = src.get("base", "#3d5929").lstrip("#")
    rgb = [int(hexv[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    out = []
    for channel, mul in zip(rgb, jitter):
        out.append(max(0, min(255, int(channel * mul * 255))))
    name = "foliage_t{:02x}{:02x}{:02x}".format(*out)
    if name not in C.MATS:
        spec = dict(src)
        spec["base"] = "#{:02x}{:02x}{:02x}".format(*out)
        C.make_pbr(name, **spec)
    mat = C.MATS[name]
    _TINT_MATS[key] = mat
    return mat


def _build_stump(name, R, col):
    """A cut stump for a slot whose tree was removed."""
    import bmesh as _bmesh
    bm = _bmesh.new()
    h = R.uniform(0.22, 0.55)
    r = R.uniform(0.13, 0.26)
    seg = 8
    ring_b, ring_t = [], []
    for i in range(seg):
        a = 2.0 * math.pi * i / seg
        wobble = 1.0 + 0.14 * math.sin(a * 3.0 + R.random())
        ring_b.append(bm.verts.new((r * wobble * math.cos(a),
                                    r * wobble * math.sin(a), 0.0)))
        ring_t.append(bm.verts.new((r * 0.88 * wobble * math.cos(a),
                                    r * 0.88 * wobble * math.sin(a),
                                    h * R.uniform(0.92, 1.08))))
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((ring_b[i], ring_b[j], ring_t[j], ring_t[i]))
    bm.faces.new(ring_t)
    _bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(C.M("bark"))
    ob = bpy.data.objects.new(name, me)
    C.link_object(ob, col)
    return ob


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
    # more silhouettes per species: the old palette gave street frontages
    # three shapes to repeat, which is what read as wallpaper.
    plan = [("street_plane", 5), ("street_maple", 5), ("park_oak", 4),
            ("poplar", 3), ("conifer", 3), ("sapling", 3), ("bare", 3)]
    if C.is_la():
        # broadleaf shade trees only; palms come from la_style.py
        plan = [("street_plane", 4), ("street_maple", 4), ("park_oak", 4),
                ("sapling", 2), ("bare", 2)]
    out = []
    for species, n in plan:
        for i in range(n):
            parts = build_tree("Tree_{}_{}".format(species, i), species, R, src_col)
            for p in parts:
                p.hide_render = True
                p.hide_viewport = True
            out.append((species, parts))
    return out


def _instance(parts, name, col, loc, rot, scale, foliage_mat=None,
              canopy_scale=1.0, trunk_only=False):
    """Place one tree. Mesh data is shared with the grown source; only the
    object-level material slot is overridden, so per-instance colour and a
    dead/bare state cost nothing in geometry."""
    made = []
    for src in parts:
        tag = src.name.split("_")[-1]
        is_canopy = tag.lower().startswith("leaves") or tag.lower().startswith("canopy")
        if trunk_only and is_canopy:
            continue
        ob = bpy.data.objects.new(name + "_" + tag, src.data)
        ob.location = loc
        ob.rotation_euler = (0.0, 0.0, rot)
        sc = scale * (canopy_scale if is_canopy else 1.0)
        ob.scale = (sc, sc, sc)
        C.link_object(ob, col)
        if is_canopy and foliage_mat is not None and ob.material_slots:
            for slot in ob.material_slots:
                slot.link = "OBJECT"
                slot.material = foliage_mat
        made.append(ob)
    return made


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
    n_stump = 0
    n_empty = 0
    spacing = 11.0          # nominal street-tree spacing, jittered below
    sw = U["sidewalk"]

    def district_at(x, y):
        """Nearest block's district, so a pit inherits its street's planting."""
        best, bestd = "midtown", 1e18
        for blk in plan["blocks"]:
            d = (blk["cx"] - x) ** 2 + (blk["cy"] - y) ** 2
            if d < bestd:
                bestd, best = d, blk.get("district", "midtown")
        return best

    def plant(x, y, district, name, park=False):
        """Place one slot: tree, stump or nothing, with health and tint."""
        nonlocal n, n_stump, n_empty

        if not park and R.random() < EMPTY_PIT.get(district, 0.08):
            if R.random() < STUMP_SHARE:
                _build_stump("Stump_{:04d}".format(n_stump), R, col)
                n_stump += 1
            else:
                n_empty += 1
            return

        mix = DISTRICT_MIX.get(district, DISTRICT_MIX["midtown"])
        # LA grows a smaller palette, so drop species that were never grown
        # rather than silently collapsing them all onto one fallback.
        mix = [(sp, w) for (sp, w) in mix if by_species.get(sp)]
        if not mix:
            mix = [(sp, 1) for sp in by_species]
        species = _weighted(mix, R)
        parts = by_species.get(species)
        if not parts:
            return
        parts = R.choice(parts)

        state, _w, canopy_scale, tint, trunk_only = _health(R)
        if species == "bare":
            trunk_only = True
        spec = SPECIES.get(species, {})
        leaf = spec.get("leaf")
        base_leaf = leaf[0] if leaf else "foliage"
        mat = None if trunk_only else _tinted_foliage(base_leaf, tint, R)

        scale = R.uniform(0.80, 1.22) * (1.14 if park else 1.0)
        _instance(parts, name.format(n), col,
                  (x + R.gauss(0, 0.14), y + R.gauss(0, 0.14), BASE_Z),
                  R.uniform(0, math.tau), scale,
                  foliage_mat=mat, canopy_scale=canopy_scale,
                  trunk_only=trunk_only)
        n += 1

    # --- street trees -----------------------------------------------------
    # The sidewalk module already cuts real tree pits; use them when present so
    # trunks land in the pits instead of through paving.
    pits = C.get_asset("tree_pits", [])
    if pits:
        for (x, y) in pits:
            if C.is_la() and C.la_palm_slot(x, y):
                continue          # this slot belongs to a palm (la_style.py)
            if R.random() > 0.94 * density:
                continue
            plant(x, y, district_at(x, y), "Tree_{:04d}")
    else:
        # fallback: walk each frontage with wandering spacing. Real planting
        # skips driveways, hydrants and crossings, so the gap between trees
        # is irregular - stepping by a jittered interval reproduces that far
        # better than an evenly divided count.
        for blk in plan["blocks"]:
            cx, cy, bw, bh = blk["cx"], blk["cy"], blk["w"], blk["h"]
            district = blk.get("district", "midtown")
            if district == "industrial" and R.random() < 0.45:
                continue
            for (along, cross, horiz) in ((bw, bh, True), (bh, bw, False)):
                for sgn in (-1, 1):
                    pos = -along * 0.5 + R.uniform(1.5, spacing)
                    while pos < along * 0.5 - 1.0:
                        gap = spacing * R.uniform(0.62, 1.65)
                        if R.random() < 0.10:
                            gap += spacing * R.uniform(0.8, 1.8)   # driveway
                        if R.random() <= 0.80 * density:
                            if horiz:
                                x = cx + pos
                                y = cy + sgn * (cross * 0.5 + sw * 0.42)
                            else:
                                y = cy + pos
                                x = cx + sgn * (cross * 0.5 + sw * 0.42)
                            if abs(x) <= half and abs(y) <= half:
                                if not (C.is_la() and C.la_palm_slot(x, y)):
                                    plant(x, y, district, "Tree_{:04d}")
                        pos += gap

    # --- parks: mixed stands, bigger canopies ----------------------------
    for park in plan.get("parks", []):
        x0, x1 = park["x0"], park["x1"]
        y0, y1 = park["y0"], park["y1"]
        area = max(1.0, (x1 - x0) * (y1 - y0))
        for _ in range(int(max(6, area / 90.0) * density)):
            x = R.uniform(x0 + 3.0, x1 - 3.0)
            y = R.uniform(y0 + 3.0, y1 - 3.0)
            # keep the centre of the park open, as the bush pass does
            if (x - park["cx"]) ** 2 + (y - park["cy"]) ** 2 < 36.0:
                continue
            plant(x, y, "residential", "Tree_park_{:04d}", park=True)

    print("  trees: {} instances from {} grown variants "
          "({} stumps, {} empty pits, {} tints)".format(
              n, len(variants), n_stump, n_empty, len(_TINT_MATS)))
    return n


if __name__ == "__main__":
    C.bootstrap(banner="M19 TREES")
    C.build_all_materials()
    build()
    C.report()
