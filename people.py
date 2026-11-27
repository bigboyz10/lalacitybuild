# =============================================================================
#  CITY BUILD  --  M16 : PEOPLE
#  Closes critique item 8: "No people. A AAA street scene at eye level needs
#  figures, even as low-detail impostors, or it reads as a model village."
#
#  Anatomically proportioned low-poly figures (8 heads tall, real limb ratios)
#  posed standing / walking / sitting / leaning, scattered on sidewalks, at
#  crossings, bus stops, benches and plazas.  Each silhouette is built once and
#  linked-duplicated, so a thousand pedestrians cost one mesh each.
#
#  standalone:  blender -b -P people.py -- --seed 7
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

# real human proportions, metres
HEIGHTS = (1.58, 1.92)          # adult range
HEAD_RATIO = 1.0 / 7.6          # head height as fraction of total

# Children are not scaled-down adults: the head is a far larger fraction of
# height and the legs a smaller one. These are the standard artistic ratios.
#   age        height (m)      heads tall
AGES = {
    "adult":   ((1.58, 1.92), 7.6, 0.52),   # (height range, heads, hip/height)
    "teen":    ((1.42, 1.62), 7.0, 0.50),
    "child":   ((1.05, 1.32), 6.0, 0.47),
    "toddler": ((0.80, 0.96), 4.6, 0.44),
}

SKIN = ["#f0d4bb", "#e8c39e", "#d9a878", "#b57f54", "#8d5a3b", "#6b4430", "#4a2f22"]
HAIR = ["#1b1410", "#2e2018", "#4a3425", "#6b4a2d", "#8a6a3f", "#2b2b2b", "#7d7d7d"]
TOPS = ["#2b3a52", "#5a1f1f", "#1f4036", "#6b5a2a", "#3b2b4a", "#8a8a8a", "#d9d9d9",
        "#1a1a1a", "#36566e", "#7a3b2a", "#2f5d3a", "#b05a2a", "#404a58", "#6a2f4a"]
BOTTOMS = ["#232a33", "#2f2f38", "#4a4336", "#1d2733", "#3a3a3a", "#55504a", "#2a3a2a"]


class Figure:
    """bmesh builder for one human silhouette."""

    def __init__(self):
        self.bm = bmesh.new()
        self.layers = []           # (face_indices, material_name)

    # ---- primitives ------------------------------------------------------
    def _tag(self, faces_before, mat):
        self.layers.append((faces_before, len(self.bm.faces), mat))

    def box(self, c, s, rot=0.0, mat=None, taper=1.0):
        before = len(self.bm.faces)
        ca, sa = math.cos(rot), math.sin(rot)
        hx, hy, hz = s[0] * 0.5, s[1] * 0.5, s[2] * 0.5
        corners = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        bot, top = [], []
        for (px, py) in corners:
            wx = c[0] + px * ca - py * sa
            wy = c[1] + px * sa + py * ca
            bot.append(self.bm.verts.new((wx, wy, c[2] - hz)))
        for (px, py) in corners:
            px, py = px * taper, py * taper
            wx = c[0] + px * ca - py * sa
            wy = c[1] + px * sa + py * ca
            top.append(self.bm.verts.new((wx, wy, c[2] + hz)))
        self.bm.faces.new(list(reversed(bot)))
        self.bm.faces.new(top)
        for i in range(4):
            j = (i + 1) % 4
            self.bm.faces.new((bot[i], bot[j], top[j], top[i]))
        self._tag(before, mat)

    def limb(self, a, b, r0, r1=None, seg=6, mat=None):
        """Tapered capsule between two points - arms, legs, neck."""
        before = len(self.bm.faces)
        r1 = r0 if r1 is None else r1
        va, vb = Vector(a), Vector(b)
        axis = vb - va
        length = axis.length
        if length < 1e-5:
            return
        quat = axis.to_track_quat('Z', 'Y')
        mat_rot = quat.to_matrix().to_4x4()
        bot, top = [], []
        for i in range(seg):
            ang = 2.0 * math.pi * i / seg
            bot.append(self.bm.verts.new(va + (mat_rot @ Vector((r0 * math.cos(ang), r0 * math.sin(ang), 0.0)))))
            top.append(self.bm.verts.new(va + (mat_rot @ Vector((r1 * math.cos(ang), r1 * math.sin(ang), length)))))
        for i in range(seg):
            j = (i + 1) % seg
            self.bm.faces.new((bot[i], bot[j], top[j], top[i]))
        self.bm.faces.new(list(reversed(bot)))
        self.bm.faces.new(top)
        self._tag(before, mat)

    def sphere(self, c, r, seg=8, rings=5, squash=1.0, mat=None):
        before = len(self.bm.faces)
        verts = []
        for ri in range(rings + 1):
            phi = math.pi * ri / rings
            row = []
            for si in range(seg):
                th = 2.0 * math.pi * si / seg
                row.append(self.bm.verts.new((
                    c[0] + r * math.sin(phi) * math.cos(th),
                    c[1] + r * math.sin(phi) * math.sin(th),
                    c[2] + r * math.cos(phi) * squash)))
            verts.append(row)
        for ri in range(rings):
            for si in range(seg):
                sj = (si + 1) % seg
                try:
                    self.bm.faces.new((verts[ri][si], verts[ri][sj],
                                       verts[ri + 1][sj], verts[ri + 1][si]))
                except ValueError:
                    pass
        self._tag(before, mat)

    def finish(self, name, collection, mats):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name + "_mesh")
        self.bm.to_mesh(me)
        self.bm.free()
        # assign material slots per tagged region
        slot_index = {}
        for mat_name in mats:
            if mat_name not in slot_index:
                slot_index[mat_name] = len(me.materials)
                me.materials.append(C.M(mat_name))
        for (f0, f1, mat_name) in self.layers:
            if mat_name is None:
                continue
            idx = slot_index.get(mat_name, 0)
            for fi in range(f0, min(f1, len(me.polygons))):
                me.polygons[fi].material_index = idx
        ob = bpy.data.objects.new(name, me)
        C.link_object(ob, collection)
        return ob


def _prop_materials():
    """Materials for carried items and vehicles.

    Registered here rather than in core.PALETTE because core.py is shared with
    other agents; keeping them local avoids a merge conflict over a table.
    """
    for nm, hexv, rough, metal in (
            ("fabric_dark", "#2a2a30", 0.88, 0.0),
            ("plastic_white", "#e8e6e0", 0.45, 0.0),
    ):
        if nm not in C.MATS:
            C.make_pbr(nm, base=hexv, roughness=rough, metallic=metal,
                       bump=0.05, grime=0.18, var_noise=1.2)


def _materials(R):
    """Register a palette of per-person materials and return chosen names."""
    skin = R.choice(SKIN)
    hair = R.choice(HAIR)
    top = R.choice(TOPS)
    bottom = R.choice(BOTTOMS)
    names = {}
    for label, hexv, rough in (("skin", skin, 0.55), ("hair", hair, 0.80),
                               ("top", top, 0.78), ("bottom", bottom, 0.72),
                               ("shoe", "#1a1a1a", 0.55)):
        nm = "person_{}_{}".format(label, hexv.lstrip("#"))
        if nm not in C.MATS:
            C.make_pbr(nm, base=hexv, roughness=rough, bump=0.06,
                       grime=0.12, var_noise=1.5)
        names[label] = nm
    return names


def build_figure(name, R, collection, pose="stand", age="adult", prop=None,
                 phase=None):
    """One proportioned human.

    pose  : stand | walk | sit | lean | phone | push | wheelchair | cycle
    age   : adult | teen | child | toddler  (real head-to-height ratios)
    prop  : None | bag | backpack | briefcase | umbrella | cup | stroller
    phase : 0..1 gait phase; None picks one at random so a crowd is not
            frozen in a single identical stride
    """
    (lo, hi), heads, hip_ratio = AGES.get(age, AGES["adult"])
    h = R.uniform(lo, hi)
    M = _materials(R)
    f = Figure()

    head_ratio = 1.0 / heads
    head_h = h * head_ratio
    head_r = head_h * 0.42
    eye_z = h - head_h * 0.55
    shoulder_z = h - head_h * 1.55
    hip_z = h * hip_ratio
    knee_z = h * 0.28
    ankle_z = h * 0.045
    shoulder_w = h * 0.115
    hip_w = h * 0.085
    depth = h * 0.085

    # A crowd where every walker is mid-stride at exactly the same angle reads
    # as a shop-window display. Sample a gait phase so legs and arms spread
    # across the whole cycle, including near-passing feet.
    if phase is None:
        phase = R.random()
    swing = math.sin(phase * math.tau)

    base_stride = {"stand": 0.0, "walk": h * 0.15, "sit": 0.0,
                   "lean": h * 0.04, "phone": h * 0.02, "push": h * 0.11,
                   "wheelchair": 0.0, "cycle": 0.0}.get(pose, 0.0)
    stride = base_stride * swing
    arm_swing = {"stand": 0.015, "walk": h * 0.11, "sit": 0.02,
                 "lean": 0.03, "phone": 0.0, "push": 0.0,
                 "wheelchair": 0.0, "cycle": 0.0}.get(pose, 0.02) * swing

    if pose in ("sit", "wheelchair"):
        hip_z = h * 0.30
        knee_z = h * 0.30
        shoulder_z = hip_z + h * 0.30
        eye_z = shoulder_z + head_h * 1.0
    elif pose == "cycle":
        hip_z = h * 0.62
        knee_z = h * 0.42
        shoulder_z = hip_z + h * 0.26
        eye_z = shoulder_z + head_h * 1.05

    # torso: chest tapering to waist
    chest_z = (shoulder_z + hip_z) * 0.5
    f.box((0, 0, chest_z), (shoulder_w * 2.0, depth * 1.6, shoulder_z - hip_z),
          mat=M["top"], taper=0.84)
    # hips
    f.box((0, 0, hip_z - h * 0.03), (hip_w * 2.0, depth * 1.5, h * 0.09),
          mat=M["bottom"])

    # neck + head
    f.limb((0, 0, shoulder_z - h * 0.01), (0, 0, shoulder_z + head_h * 0.30),
           head_r * 0.42, head_r * 0.40, seg=6, mat=M["skin"])
    f.sphere((0, 0, eye_z), head_r, seg=8, rings=5, squash=1.18, mat=M["skin"])
    # hair cap
    f.sphere((0, -head_r * 0.06, eye_z + head_r * 0.22), head_r * 0.98,
             seg=8, rings=4, squash=0.80, mat=M["hair"])

    # legs
    for side, sgn in (("l", -1), ("r", 1)):
        fwd = stride if sgn > 0 else -stride
        hx = sgn * hip_w * 0.55
        if pose in ("sit", "wheelchair"):
            knee = (hx, depth * 2.2, knee_z)
            ankle = (hx, depth * 3.0, ankle_z)
        elif pose == "cycle":
            # one leg down on the pedal, one up, offset by half a revolution
            crank = phase + (0.0 if sgn > 0 else 0.5)
            px = math.cos(crank * math.tau) * h * 0.09
            pz = math.sin(crank * math.tau) * h * 0.09
            knee = (hx, depth * 1.6, knee_z + h * 0.06)
            ankle = (hx, depth * 1.9 + px, h * 0.20 + pz)
        else:
            knee = (hx, fwd * 0.55, knee_z)
            ankle = (hx, fwd, ankle_z)
        f.limb((hx, 0, hip_z), knee, h * 0.055, h * 0.040, seg=6, mat=M["bottom"])
        f.limb(knee, ankle, h * 0.040, h * 0.030, seg=6, mat=M["bottom"])
        # shoe
        f.box((ankle[0], ankle[1] + h * 0.025, ankle_z * 0.55),
              (h * 0.052, h * 0.105, h * 0.035), mat=M["shoe"])

    # arms
    for side, sgn in (("l", -1), ("r", 1)):
        fwd = -arm_swing if sgn > 0 else arm_swing
        sx = sgn * shoulder_w * 0.98
        elbow = (sx * 1.04, fwd * 0.5, shoulder_z - h * 0.155)
        carry_side = (sgn > 0)
        if pose == "phone" and sgn > 0:
            hand = (sx * 0.55, depth * 1.9, shoulder_z - h * 0.13)
        elif pose in ("sit", "wheelchair"):
            hand = (sx * 1.0, depth * 1.6, hip_z + h * 0.02)
        elif pose == "push":
            hand = (sx * 0.85, depth * 4.2, hip_z + h * 0.16)
        elif pose == "cycle":
            hand = (sx * 0.80, depth * 4.0, shoulder_z - h * 0.02)
        elif prop in ("bag", "briefcase") and carry_side:
            hand = (sx * 1.06, 0.0, hip_z + h * 0.06)
        elif prop == "umbrella" and carry_side:
            hand = (sx * 0.70, depth * 1.2, shoulder_z - h * 0.02)
        elif prop == "cup" and carry_side:
            hand = (sx * 0.62, depth * 1.7, shoulder_z - h * 0.16)
        else:
            hand = (sx * 1.02, fwd, shoulder_z - h * 0.30)
        f.limb((sx, 0, shoulder_z), elbow, h * 0.042, h * 0.034, seg=5, mat=M["top"])
        f.limb(elbow, hand, h * 0.034, h * 0.026, seg=5, mat=M["skin"])

    _add_prop(f, R, M, h, hip_z, shoulder_z, shoulder_w, depth, prop, pose, head_r)

    mats = list(set(M.values())) + ["fabric_dark", "metal_dark", "rubber"]
    return f.finish(name, collection, mats)


def _add_prop(f, R, M, h, hip_z, shoulder_z, shoulder_w, depth, prop, pose,
              head_r):
    """Carried objects and the wheelchair / bicycle a figure sits on."""
    sx = shoulder_w * 1.10

    if prop == "bag":
        f.box((sx * 1.05, 0.0, hip_z - h * 0.06),
              (h * 0.11, h * 0.055, h * 0.16), mat="fabric_dark")
        f.limb((sx * 1.05, 0, hip_z + h * 0.02),
               (sx * 1.05, 0, hip_z + h * 0.08), h * 0.004, h * 0.004,
               seg=4, mat="fabric_dark")
    elif prop == "briefcase":
        f.box((sx * 1.05, 0.0, hip_z - h * 0.09),
              (h * 0.06, h * 0.17, h * 0.13), mat="fabric_dark")
    elif prop == "backpack":
        f.box((0.0, -depth * 1.9, (shoulder_z + hip_z) * 0.5),
              (shoulder_w * 1.5, depth * 1.1, h * 0.22), mat="fabric_dark")
    elif prop == "cup":
        f.limb((sx * 0.62, depth * 1.7, shoulder_z - h * 0.155),
               (sx * 0.62, depth * 1.7, shoulder_z - h * 0.115),
               h * 0.018, h * 0.015, seg=6, mat="plastic_white")
    elif prop == "umbrella":
        top = shoulder_z + h * 0.30
        f.limb((sx * 0.70, depth * 1.2, shoulder_z - h * 0.02),
               (sx * 0.70, depth * 1.2, top), h * 0.006, h * 0.006,
               seg=5, mat="metal_dark")
        # canopy: shallow cone
        f.limb((sx * 0.70, depth * 1.2, top - h * 0.05),
               (sx * 0.70, depth * 1.2, top + h * 0.02),
               h * 0.33, h * 0.02, seg=8, mat="fabric_dark")

    if pose == "push":
        # pram: body, hood, handle, four small wheels
        y = depth * 4.4
        f.box((0.0, y, hip_z + h * 0.02), (h * 0.20, h * 0.34, h * 0.20),
              mat="fabric_dark")
        f.box((0.0, y - h * 0.10, hip_z + h * 0.16),
              (h * 0.19, h * 0.14, h * 0.14), mat="fabric_dark")
        f.limb((0.0, y - h * 0.18, hip_z + h * 0.16),
               (0.0, depth * 3.4, hip_z + h * 0.18),
               h * 0.008, h * 0.008, seg=5, mat="metal_dark")
        for dx in (-1, 1):
            for dy in (-1, 1):
                cx = dx * h * 0.085
                cy = y + dy * h * 0.13
                f.limb((cx - h * 0.012, cy, h * 0.055),
                       (cx + h * 0.012, cy, h * 0.055),
                       h * 0.048, h * 0.048, seg=7, mat="rubber")
    elif pose == "wheelchair":
        for dx in (-1, 1):
            cx = dx * (shoulder_w * 1.15)
            f.limb((cx - h * 0.018, depth * 1.2, h * 0.30),
                   (cx + h * 0.018, depth * 1.2, h * 0.30),
                   h * 0.29, h * 0.29, seg=12, mat="rubber")
            f.limb((cx - h * 0.012, depth * 3.4, h * 0.10),
                   (cx + h * 0.012, depth * 3.4, h * 0.10),
                   h * 0.09, h * 0.09, seg=8, mat="rubber")
        f.box((0.0, depth * 2.0, h * 0.285), (shoulder_w * 2.0, h * 0.30,
              h * 0.03), mat="metal_dark")
        f.box((0.0, depth * 0.2, h * 0.42), (shoulder_w * 2.0, h * 0.03,
              h * 0.28), mat="fabric_dark")
    elif pose == "cycle":
        # frame, wheels, bars - a bike read at street distance
        for dy, rad in ((depth * 5.2, h * 0.34), (-depth * 3.2, h * 0.34)):
            f.limb((-h * 0.012, dy, rad),
                   ( h * 0.012, dy, rad), rad, rad, seg=14, mat="rubber")
        f.limb((0.0, -depth * 3.2, h * 0.34), (0.0, depth * 1.4, h * 0.52),
               h * 0.012, h * 0.012, seg=5, mat="metal_dark")
        f.limb((0.0, depth * 1.4, h * 0.52), (0.0, depth * 5.2, h * 0.34),
               h * 0.012, h * 0.012, seg=5, mat="metal_dark")
        f.limb((0.0, depth * 1.4, h * 0.52), (0.0, depth * 1.4, h * 0.62),
               h * 0.010, h * 0.010, seg=5, mat="metal_dark")
        f.limb((-shoulder_w * 0.95, depth * 4.3, h * 0.66),
               ( shoulder_w * 0.95, depth * 4.3, h * 0.66),
               h * 0.010, h * 0.010, seg=5, mat="metal_dark")


# -----------------------------------------------------------------------------
def _variants(R, collection, n=30):
    """Build a palette of base figures to linked-duplicate from.

    Wider than the original 14: every (pose, age, prop) combination is a
    distinct silhouette, which is what stops a crowd reading as clones.
    """
    _prop_materials()
    specs = [
        # (pose, age, prop, weight)
        ("walk", "adult", None, 10),
        ("walk", "adult", "bag", 6),
        ("walk", "adult", "backpack", 5),
        ("walk", "adult", "briefcase", 3),
        ("walk", "adult", "cup", 3),
        ("walk", "teen", "backpack", 4),
        ("walk", "child", None, 3),
        ("walk", "child", "backpack", 2),
        ("stand", "adult", None, 5),
        ("stand", "adult", "bag", 3),
        ("stand", "adult", "umbrella", 2),
        ("stand", "child", None, 2),
        ("stand", "toddler", None, 2),
        ("phone", "adult", None, 5),
        ("phone", "teen", "backpack", 2),
        ("lean", "adult", None, 3),
        ("lean", "teen", None, 2),
        ("sit", "adult", None, 4),
        ("sit", "adult", "bag", 2),
        ("sit", "child", None, 2),
        ("push", "adult", None, 3),
        ("wheelchair", "adult", None, 2),
        ("cycle", "adult", None, 3),
        ("cycle", "teen", "backpack", 2),
    ]
    out = []
    i = 0
    for (pose, age, prop, weight) in specs:
        copies = max(1, round(weight * n / 80.0))
        for _ in range(copies):
            ob = build_figure("Person_src_{:03d}".format(i), R, collection,
                              pose=pose, age=age, prop=prop)
            ob.hide_render = True
            ob.hide_viewport = True
            out.append({"ob": ob, "pose": pose, "age": age,
                        "prop": prop, "weight": weight})
            i += 1
    return out


def _pick(R, variants, poses=None, ages=None):
    pool = [v for v in variants
            if (poses is None or v["pose"] in poses)
            and (ages is None or v["age"] in ages)]
    if not pool:
        pool = variants
    total = sum(v["weight"] for v in pool)
    t = R.uniform(0.0, total)
    acc = 0.0
    for v in pool:
        acc += v["weight"]
        if t <= acc:
            return v
    return pool[-1]


def _dup(src, name, collection, loc, rot, scale=1.0):
    ob = bpy.data.objects.new(name, src.data)
    ob.location = loc
    ob.rotation_euler = (0.0, 0.0, rot)
    ob.scale = (scale, scale, scale)
    C.link_object(ob, collection)
    return ob


def build():
    R = rng("people")
    plan = plan_city()
    col = C.col("CITY_People")
    src_col = C.col("CITY_People_src")

    variants = _variants(R, src_col)
    half = plan["half"]
    sw = U["sidewalk"]
    density = CONFIG.get("density", 0.8)
    n = 0

    def put(v, x, y, rot, z=BASE_Z, scale=1.0):
        nonlocal n
        if abs(x) > half or abs(y) > half:
            return False
        _dup(v["ob"], "Person_{:04d}".format(n), col, (x, y, z), rot,
             scale=scale * R.uniform(0.97, 1.03))
        n += 1
        return True

    # --- pedestrians along sidewalk edges --------------------------------
    for blk in plan["blocks"]:
        cx, cy = blk["cx"], blk["cy"]
        bw, bh = blk["w"], blk["h"]
        district = blk.get("district", "midtown")
        base = {"downtown": 15, "midtown": 10, "waterfront": 7,
                "residential": 6, "industrial": 3}.get(district, 7)
        count = int(base * density * R.uniform(0.55, 1.45))

        for _ in range(count):
            edge = R.randint(0, 3)
            inset = R.uniform(0.9, sw - 0.7)
            if edge == 0:
                x = cx + R.uniform(-bw * 0.5, bw * 0.5); y = cy - bh * 0.5 - inset
                rot = R.gauss(math.pi * 0.5, 0.5)
            elif edge == 1:
                x = cx + R.uniform(-bw * 0.5, bw * 0.5); y = cy + bh * 0.5 + inset
                rot = R.gauss(-math.pi * 0.5, 0.5)
            elif edge == 2:
                x = cx - bw * 0.5 - inset; y = cy + R.uniform(-bh * 0.5, bh * 0.5)
                rot = R.gauss(0.0, 0.5)
            else:
                x = cx + bw * 0.5 + inset; y = cy + R.uniform(-bh * 0.5, bh * 0.5)
                rot = R.gauss(math.pi, 0.5)

            v = _pick(R, variants, poses=("walk", "stand", "phone", "push"))
            if not put(v, x, y, rot):
                continue

            # an adult with a child walks beside them, not on top of them
            if v["age"] == "adult" and v["pose"] == "walk" and R.random() < 0.14:
                child = _pick(R, variants, poses=("walk",),
                              ages=("child", "toddler"))
                off = 0.55 + R.uniform(0.0, 0.25)
                put(child, x + math.cos(rot + math.pi * 0.5) * off,
                    y + math.sin(rot + math.pi * 0.5) * off,
                    rot + R.gauss(0.0, 0.18))

    # --- conversation groups: people actually facing each other ----------
    groups = int(10 * density)
    for _ in range(groups):
        gx = R.uniform(-half * 0.92, half * 0.92)
        gy = R.uniform(-half * 0.92, half * 0.92)
        size = R.choice([2, 2, 3, 3, 4])
        radius = 0.45 + 0.17 * size
        start = R.uniform(0.0, math.tau)
        for k in range(size):
            ang = start + math.tau * k / size + R.gauss(0.0, 0.10)
            px = gx + math.cos(ang) * radius
            py = gy + math.sin(ang) * radius
            # face the centre of the circle
            facing = math.atan2(gy - py, gx - px)
            v = _pick(R, variants, poses=("stand", "phone"))
            put(v, px, py, facing)

    # --- clusters waiting at crossings -----------------------------------
    for it in plan["intersections"]:
        if R.random() > 0.55:
            continue
        kerb = it["w"] * 0.5 + R.uniform(1.2, 2.6)
        for _ in range(R.randint(2, 6)):
            ang = R.uniform(0, math.tau)
            px = it["x"] + math.cos(ang) * kerb
            py = it["y"] + math.sin(ang) * kerb
            # people waiting to cross face the road, not random directions
            facing = math.atan2(it["y"] - py, it["x"] - px) + R.gauss(0.0, 0.35)
            v = _pick(R, variants, poses=("stand", "phone", "push", "wheelchair"))
            put(v, px, py, facing)

    # --- seated figures on benches and in shelters ------------------------
    bench_like = [o for o in bpy.data.objects
                  if o.name.startswith(("Bench", "PicnicTable", "BusShelter"))]
    for ob in bench_like:
        if R.random() > 0.45:
            continue
        for _ in range(R.randint(1, 2)):
            v = _pick(R, variants, poses=("sit",))
            put(v, ob.location.x + R.uniform(-0.6, 0.6),
                ob.location.y + R.uniform(-0.25, 0.25),
                ob.rotation_euler.z + R.uniform(-0.3, 0.3))

    # --- cyclists travel in the road, aligned to it -----------------------
    for road in plan.get("roads_x", [])[:] + plan.get("roads_y", [])[:]:
        if R.random() > 0.35:
            continue
        axis = road.get("axis", "x")
        c = road.get("c", 0.0)
        for _ in range(R.randint(1, 3)):
            t = R.uniform(-half * 0.9, half * 0.9)
            lane = R.choice([-1, 1]) * (road.get("w", 10.0) * 0.5 - 1.2)
            v = _pick(R, variants, poses=("cycle",))
            if axis == "x":
                put(v, t, c + lane, 0.0 if lane < 0 else math.pi)
            else:
                put(v, c + lane, t, math.pi * 0.5 if lane < 0 else -math.pi * 0.5)

    # --- leaners against walls --------------------------------------------
    for _ in range(int(14 * density)):
        v = _pick(R, variants, poses=("lean",))
        put(v, R.uniform(-half, half), R.uniform(-half, half),
            R.uniform(0, math.tau))

    kinds = {}
    for v in variants:
        key = "{}/{}".format(v["pose"], v["age"])
        kinds[key] = kinds.get(key, 0) + 1
    print("  people: {} figures from {} silhouettes "
          "({} poses x 4 ages, {} prop types)".format(
              n, len(variants),
              len({v["pose"] for v in variants}),
              len({v["prop"] for v in variants if v["prop"]})))
    return n


if __name__ == "__main__":
    C.bootstrap(banner="M16 PEOPLE")
    C.build_all_materials()
    build()
    C.report()
