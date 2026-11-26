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


def build_figure(name, R, collection, pose="stand"):
    """One proportioned human. pose: stand | walk | sit | lean | phone."""
    h = R.uniform(*HEIGHTS)
    M = _materials(R)
    f = Figure()

    head_h = h * HEAD_RATIO
    head_r = head_h * 0.42
    eye_z = h - head_h * 0.55
    shoulder_z = h - head_h * 1.55
    hip_z = h * 0.52
    knee_z = h * 0.28
    ankle_z = h * 0.045
    shoulder_w = h * 0.115
    hip_w = h * 0.085
    depth = h * 0.085

    stride = {"stand": 0.0, "walk": h * 0.14, "sit": 0.0,
              "lean": h * 0.04, "phone": 0.0}[pose]
    arm_swing = {"stand": 0.015, "walk": h * 0.10, "sit": 0.02,
                 "lean": 0.03, "phone": 0.0}[pose]

    if pose == "sit":
        hip_z = h * 0.30
        knee_z = h * 0.30
        shoulder_z = hip_z + h * 0.30
        eye_z = shoulder_z + head_h * 1.0

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
        if pose == "sit":
            knee = (hx, depth * 2.2, knee_z)
            ankle = (hx, depth * 3.0, ankle_z)
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
        if pose == "phone" and sgn > 0:
            hand = (sx * 0.55, depth * 1.9, shoulder_z - h * 0.13)
        elif pose == "sit":
            hand = (sx * 1.0, depth * 1.6, hip_z + h * 0.02)
        else:
            hand = (sx * 1.02, fwd, shoulder_z - h * 0.30)
        f.limb((sx, 0, shoulder_z), elbow, h * 0.042, h * 0.034, seg=5, mat=M["top"])
        f.limb(elbow, hand, h * 0.034, h * 0.026, seg=5, mat=M["skin"])

    return f.finish(name, collection, list(set(M.values())))


# -----------------------------------------------------------------------------
def _variants(R, collection, n=14):
    """Build a palette of base figures to linked-duplicate from."""
    poses = ["stand", "walk", "walk", "walk", "phone", "lean", "sit"]
    out = []
    for i in range(n):
        pose = poses[i % len(poses)]
        ob = build_figure("Person_src_{:02d}".format(i), R, collection, pose=pose)
        ob.hide_render = True
        ob.hide_viewport = True
        out.append((ob, pose))
    return out


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
    walkers = [v for v in variants if v[1] in ("walk", "stand", "phone")]
    sitters = [v for v in variants if v[1] == "sit"]
    leaners = [v for v in variants if v[1] == "lean"]

    half = plan["half"]
    sw = U["sidewalk"]
    n = 0
    density = CONFIG.get("density", 0.8)

    # --- pedestrians along every sidewalk edge ---------------------------
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
            if abs(x) > half or abs(y) > half:
                continue
            src, _pose = R.choice(walkers)
            _dup(src, "Person_{:04d}".format(n), col, (x, y, BASE_Z),
                 rot, scale=R.uniform(0.96, 1.04))
            n += 1

    # --- clusters waiting at intersections (crossings) -------------------
    for it in plan["intersections"]:
        if R.random() > 0.55:
            continue
        for _ in range(R.randint(2, 6)):
            ang = R.uniform(0, math.tau)
            rad = it["w"] * 0.5 + R.uniform(1.2, 3.0)
            x = it["x"] + math.cos(ang) * rad
            y = it["y"] + math.sin(ang) * rad
            if abs(x) > half or abs(y) > half:
                continue
            src, _pose = R.choice(walkers)
            _dup(src, "Person_cross_{:04d}".format(n), col, (x, y, BASE_Z),
                 R.uniform(0, math.tau), scale=R.uniform(0.96, 1.04))
            n += 1

    # --- people sitting on benches / leaning on walls --------------------
    bench_like = [o for o in bpy.data.objects
                  if o.name.startswith(("Bench", "PicnicTable", "BusShelter"))]
    for ob in bench_like:
        if not sitters or R.random() > 0.45:
            continue
        for _ in range(R.randint(1, 2)):
            src, _pose = R.choice(sitters)
            off = Vector((R.uniform(-0.6, 0.6), R.uniform(-0.25, 0.25), 0.0))
            loc = (ob.location.x + off.x, ob.location.y + off.y, BASE_Z)
            _dup(src, "Person_sit_{:04d}".format(n), col, loc,
                 ob.rotation_euler.z + R.uniform(-0.3, 0.3))
            n += 1

    if leaners:
        for _ in range(int(18 * density)):
            x = R.uniform(-half, half); y = R.uniform(-half, half)
            src, _pose = R.choice(leaners)
            _dup(src, "Person_lean_{:04d}".format(n), col, (x, y, BASE_Z),
                 R.uniform(0, math.tau))
            n += 1

    print("  people: {} figures from {} silhouettes".format(n, len(variants)))
    return n


if __name__ == "__main__":
    C.bootstrap(banner="M16 PEOPLE")
    C.build_all_materials()
    build()
    C.report()
