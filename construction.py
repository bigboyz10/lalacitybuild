# =============================================================================
#  CITY BUILD  --  M22 : CONSTRUCTION SEQUENCING          (board task T-006)
#
#  Closes critique 4: "No construction sequencing. Cranes exist but there are
#  no half-built floors, formwork or material lay-down areas."
#
#  A city with no building sites reads as finished and therefore staged. This
#  module reserves a few lots before the buildings pass and puts a site on
#  each, at a randomly chosen stage of a real build sequence:
#
#      excavation -> substructure -> frame -> envelope -> fit-out
#
#  Each stage shows what that stage actually looks like: an open pit with
#  shoring and a ramp; a mat slab with starter bars; a concrete frame with
#  floor plates poured to a given level, columns continuing above, formwork
#  and rebar cages on the live deck; cladding creeping up the lower floors
#  behind scaffold and netting; and finally a nearly-complete envelope with
#  the scaffold coming down.
#
#  Every site also gets the things that surround real ones: hoarding with
#  gates, a stack of site cabins, material lay-down (rebar bundles, block
#  pallets, pipe stacks, aggregate piles), skips and a wheel-wash.
#
#  standalone:  blender -b -P construction.py -- --seed 5
# =============================================================================
import bmesh
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, U, rng, plan_city

BASE_Z = 0.15
FLOOR_H = 3.40

STAGES = ["excavation", "substructure", "frame", "envelope", "fitout"]
STAGE_WEIGHTS = [0.14, 0.14, 0.30, 0.26, 0.16]


# -----------------------------------------------------------------------------
# geometry helper
# -----------------------------------------------------------------------------
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

    def bar(self, a, b, r=0.03, seg=4):
        va, vb = Vector(a), Vector(b)
        axis = vb - va
        length = axis.length
        if length < 1e-5:
            return
        rot = axis.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        bot, top = [], []
        for i in range(seg):
            ang = 2.0 * math.pi * i / seg
            off = Vector((r * math.cos(ang), r * math.sin(ang), 0.0))
            bot.append(self.bm.verts.new(va + (rot @ off)))
            top.append(self.bm.verts.new(va + (rot @ (off + Vector((0, 0, length))))))
        for i in range(seg):
            j = (i + 1) % seg
            self.bm.faces.new((bot[i], bot[j], top[j], top[i]))
        self.bm.faces.new(list(reversed(bot)))
        self.bm.faces.new(top)

    def obj(self, name, mat, collection, loc=(0, 0, 0), rot=0.0):
        if not self.bm.faces:
            self.bm.free()
            return None
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


def _materials():
    for name, spec in (
        ("site_concrete",  dict(base="#9c9a94", roughness=0.88, bump=0.35, grime=0.55)),
        ("site_rebar",     dict(base="#8a5a3a", roughness=0.86, metallic=0.75, grime=0.60)),
        ("site_formwork",  dict(base="#b8966a", roughness=0.85, bump=0.30, grime=0.50)),
        ("site_scaffold",  dict(base="#b4b8bc", roughness=0.55, metallic=0.85, grime=0.40)),
        ("site_netting",   dict(base="#3f6fae", roughness=0.80, alpha=0.42)),
        ("site_hoarding",  dict(base="#2f6f4f", roughness=0.80, bump=0.18, grime=0.45)),
        ("site_cabin",     dict(base="#d8d4cb", roughness=0.70, grime=0.50)),
        ("site_soil",      dict(base="#6b5a44", roughness=0.96, bump=0.60, grime=0.70)),
        ("site_gravel",    dict(base="#8e8a82", roughness=0.95, bump=0.70, grime=0.55)),
        ("site_block",     dict(base="#a8a49c", roughness=0.90, bump=0.25)),
        ("site_hiviz",     dict(base="#e8a317", roughness=0.62)),
        ("site_skip",      dict(base="#8a4a28", roughness=0.78, metallic=0.55, grime=0.65)),
    ):
        if name not in C.MATS:
            C.make_pbr(name, **spec)


# -----------------------------------------------------------------------------
# site furniture
# -----------------------------------------------------------------------------
def _hoarding(rect, R, col, name):
    """Plywood hoarding around the lot, with a vehicle gate on one side."""
    x0, y0, x1, y1 = rect
    h = R.uniform(2.0, 2.6)
    p = Part()
    gate_side = R.randint(0, 3)
    for side in range(4):
        if side == 0:
            ax, ay, bx, by = x0, y0, x1, y0
        elif side == 1:
            ax, ay, bx, by = x1, y0, x1, y1
        elif side == 2:
            ax, ay, bx, by = x1, y1, x0, y1
        else:
            ax, ay, bx, by = x0, y1, x0, y0
        length = math.hypot(bx - ax, by - ay)
        if length < 1.0:
            continue
        panels = max(1, int(length / 2.4))
        for i in range(panels):
            t0 = i / float(panels)
            t1 = (i + 1) / float(panels)
            if side == gate_side and 0.38 < (t0 + t1) * 0.5 < 0.62:
                continue                                   # gate opening
            mx = ax + (bx - ax) * (t0 + t1) * 0.5
            my = ay + (by - ay) * (t0 + t1) * 0.5
            seg = length / panels
            rot = math.atan2(by - ay, bx - ax)
            p.box(mx, my, BASE_Z + h * 0.5, seg * 0.98, 0.08, h, rot=rot)
            p.box(mx, my, BASE_Z + h + 0.05, seg * 0.98, 0.14, 0.10, rot=rot)
    return p.obj(name, "site_hoarding", col)


def _cabins(cx, cy, R, col, name, n=2):
    p = Part()
    for i in range(n):
        w, d, h = 6.0, 2.8, 2.7
        ox = R.uniform(-1.0, 1.0)
        oy = i * (d + 0.3)
        stack = 1 if R.random() > 0.35 else 2
        for s in range(stack):
            p.box(cx + ox, cy + oy, BASE_Z + h * 0.5 + s * h, w, d, h)
    return p.obj(name, "site_cabin", col)


def _laydown(rect, R, col, prefix):
    """Rebar bundles, block pallets, pipe stacks, aggregate piles, skips."""
    x0, y0, x1, y1 = rect
    out = []
    rebar = Part()
    for _ in range(R.randint(2, 5)):
        bx = R.uniform(x0 + 2.0, x1 - 2.0)
        by = R.uniform(y0 + 2.0, y1 - 2.0)
        rot = R.uniform(0, math.pi)
        for k in range(R.randint(5, 10)):
            off = (k % 5) * 0.07
            lift = (k // 5) * 0.07
            rebar.bar((bx - math.cos(rot) * 3.0 - math.sin(rot) * off,
                       by - math.sin(rot) * 3.0 + math.cos(rot) * off,
                       BASE_Z + 0.05 + lift),
                      (bx + math.cos(rot) * 3.0 - math.sin(rot) * off,
                       by + math.sin(rot) * 3.0 + math.cos(rot) * off,
                       BASE_Z + 0.05 + lift), r=0.016, seg=4)
    out.append(rebar.obj(prefix + "_Rebar", "site_rebar", col))

    blocks = Part()
    for _ in range(R.randint(2, 5)):
        bx = R.uniform(x0 + 1.5, x1 - 1.5)
        by = R.uniform(y0 + 1.5, y1 - 1.5)
        rot = R.uniform(0, math.pi)
        layers = R.randint(3, 6)
        for lz in range(layers):
            jitter = 0.0 if lz < layers - 1 else R.uniform(-0.12, 0.12)
            blocks.box(bx + jitter, by, BASE_Z + 0.10 + lz * 0.20,
                       1.15, 1.00, 0.20, rot=rot)
        blocks.box(bx, by, BASE_Z + 0.05, 1.20, 1.05, 0.10, rot=rot)
    out.append(blocks.obj(prefix + "_Blocks", "site_block", col))

    piles = Part()
    for _ in range(R.randint(1, 3)):
        bx = R.uniform(x0 + 2.5, x1 - 2.5)
        by = R.uniform(y0 + 2.5, y1 - 2.5)
        r = R.uniform(1.6, 2.8)
        for ring, (rr, hh) in enumerate(((r, 0.25), (r * 0.66, 0.70), (r * 0.33, 1.05))):
            piles.box(bx, by, BASE_Z + hh * 0.5, rr * 2.0, rr * 2.0, hh,
                      rot=R.uniform(0, 0.8))
    out.append(piles.obj(prefix + "_Aggregate", "site_gravel", col))

    skips = Part()
    for _ in range(R.randint(1, 2)):
        bx = R.uniform(x0 + 2.0, x1 - 2.0)
        by = R.uniform(y0 + 2.0, y1 - 2.0)
        rot = R.uniform(0, math.pi)
        skips.box(bx, by, BASE_Z + 0.62, 3.6, 1.8, 1.24, rot=rot)
    out.append(skips.obj(prefix + "_Skips", "site_skip", col))
    return [o for o in out if o]


def _scaffold(rect, R, col, name, height, netted=True):
    """Tube-and-fitting scaffold with lifts, ledgers and debris netting."""
    x0, y0, x1, y1 = rect
    p = Part()
    net = Part()
    bay = 2.1
    lift = 2.0
    lifts = max(1, int(height / lift))
    perim = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
             ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    for (ax, ay), (bx, by) in perim:
        length = math.hypot(bx - ax, by - ay)
        bays = max(1, int(length / bay))
        ux, uy = (bx - ax) / length, (by - ay) / length
        nx, ny = -uy, ux
        for i in range(bays + 1):
            px = ax + ux * (length * i / bays) + nx * 0.5
            py = ay + uy * (length * i / bays) + ny * 0.5
            p.bar((px, py, BASE_Z), (px, py, BASE_Z + lifts * lift), r=0.026, seg=4)
        for lz in range(1, lifts + 1):
            z = BASE_Z + lz * lift
            p.bar((ax + nx * 0.5, ay + ny * 0.5, z),
                  (bx + nx * 0.5, by + ny * 0.5, z), r=0.022, seg=4)
        if netted:
            mx = (ax + bx) * 0.5 + nx * 0.56
            my = (ay + by) * 0.5 + ny * 0.56
            net.box(mx, my, BASE_Z + lifts * lift * 0.5, length, 0.03,
                    lifts * lift, rot=math.atan2(by - ay, bx - ax))
    objs = [p.obj(name, "site_scaffold", col)]
    if netted:
        objs.append(net.obj(name + "_Net", "site_netting", col))
    return [o for o in objs if o]


# -----------------------------------------------------------------------------
# the stages
# -----------------------------------------------------------------------------
def _excavation(rect, R, col, prefix):
    x0, y0, x1, y1 = rect
    depth = R.uniform(2.5, 5.0)
    p = Part()
    # pit floor sits below grade; spoil berm around the lip
    p.box((x0 + x1) * 0.5, (y0 + y1) * 0.5, BASE_Z - depth,
          (x1 - x0) * 0.92, (y1 - y0) * 0.92, 0.3)
    shoring = Part()
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1),
                             (x1, y1, x0, y1), (x0, y1, x0, y0)):
        length = math.hypot(bx - ax, by - ay)
        rot = math.atan2(by - ay, bx - ax)
        shoring.box((ax + bx) * 0.5, (ay + by) * 0.5, BASE_Z - depth * 0.5,
                    length, 0.25, depth, rot=rot)
        piles = max(2, int(length / 2.5))
        for i in range(piles):
            t = i / float(piles - 1 if piles > 1 else 1)
            shoring.bar((ax + (bx - ax) * t, ay + (by - ay) * t, BASE_Z - depth),
                        (ax + (bx - ax) * t, ay + (by - ay) * t, BASE_Z + 0.5),
                        r=0.10, seg=5)
    out = [p.obj(prefix + "_Pit", "site_soil", col),
           shoring.obj(prefix + "_Shoring", "site_concrete", col)]
    # haul ramp down into the pit
    ramp = Part()
    ramp.box((x0 + x1) * 0.5, y0 + (y1 - y0) * 0.18, BASE_Z - depth * 0.5,
             (x1 - x0) * 0.30, (y1 - y0) * 0.36, depth, rot=0.0)
    out.append(ramp.obj(prefix + "_Ramp", "site_soil", col))
    return [o for o in out if o], 0.0


def _substructure(rect, R, col, prefix):
    x0, y0, x1, y1 = rect
    p = Part()
    p.box((x0 + x1) * 0.5, (y0 + y1) * 0.5, BASE_Z + 0.25,
          (x1 - x0) * 0.94, (y1 - y0) * 0.94, 0.5)          # mat slab
    bars = Part()
    gx = int(max(2, (x1 - x0) / 6.0))
    gy = int(max(2, (y1 - y0) / 6.0))
    for i in range(gx + 1):
        for j in range(gy + 1):
            px = x0 + (x1 - x0) * i / gx
            py = y0 + (y1 - y0) * j / gy
            for k in range(4):                               # starter bar cage
                ox = (k % 2) * 0.22 - 0.11
                oy = (k // 2) * 0.22 - 0.11
                bars.bar((px + ox, py + oy, BASE_Z + 0.5),
                         (px + ox, py + oy, BASE_Z + R.uniform(1.0, 1.8)),
                         r=0.016, seg=4)
    return [o for o in (p.obj(prefix + "_MatSlab", "site_concrete", col),
                        bars.obj(prefix + "_Starters", "site_rebar", col)) if o], 0.5


def _frame(rect, R, col, prefix, floors):
    """Poured floor plates, columns continuing above, formwork on the live deck."""
    x0, y0, x1, y1 = rect
    w, d = x1 - x0, y1 - y0
    cols_x = max(2, int(w / 7.0))
    cols_y = max(2, int(d / 7.0))

    slabs = Part()
    columns = Part()
    for f in range(floors + 1):
        z = BASE_Z + f * FLOOR_H
        slabs.box((x0 + x1) * 0.5, (y0 + y1) * 0.5, z + 0.12,
                  w * 0.96, d * 0.96, 0.24)
    for i in range(cols_x + 1):
        for j in range(cols_y + 1):
            px = x0 + w * i / cols_x
            py = y0 + d * j / cols_y
            columns.box(px, py, BASE_Z + (floors + 0.6) * FLOOR_H * 0.5,
                        0.45, 0.45, (floors + 0.6) * FLOOR_H)

    # live deck: formwork panels, props underneath, rebar mat on top
    deck_z = BASE_Z + floors * FLOOR_H
    form = Part()
    props_ = Part()
    mat = Part()
    for i in range(cols_x):
        for j in range(cols_y):
            if R.random() > 0.72:
                continue
            px = x0 + w * (i + 0.5) / cols_x
            py = y0 + d * (j + 0.5) / cols_y
            form.box(px, py, deck_z + FLOOR_H - 0.10,
                     w / cols_x * 0.9, d / cols_y * 0.9, 0.08)
            for k in range(4):
                ox = (k % 2 - 0.5) * w / cols_x * 0.5
                oy = (k // 2 - 0.5) * d / cols_y * 0.5
                props_.bar((px + ox, py + oy, deck_z + 0.12),
                           (px + ox, py + oy, deck_z + FLOOR_H - 0.14),
                           r=0.035, seg=4)
    step = 0.9
    nx = max(2, int(w / step))
    ny = max(2, int(d / step))
    for i in range(nx + 1):
        px = x0 + w * i / nx
        mat.bar((px, y0 + 0.4, deck_z + FLOOR_H + 0.02),
                (px, y1 - 0.4, deck_z + FLOOR_H + 0.02), r=0.012, seg=3)
    for j in range(ny + 1):
        py = y0 + d * j / ny
        mat.bar((x0 + 0.4, py, deck_z + FLOOR_H + 0.05),
                (x1 - 0.4, py, deck_z + FLOOR_H + 0.05), r=0.012, seg=3)

    out = [slabs.obj(prefix + "_Slabs", "site_concrete", col),
           columns.obj(prefix + "_Columns", "site_concrete", col),
           form.obj(prefix + "_Formwork", "site_formwork", col),
           props_.obj(prefix + "_Props", "site_scaffold", col),
           mat.obj(prefix + "_RebarMat", "site_rebar", col)]
    return [o for o in out if o], (floors + 1) * FLOOR_H


def _envelope(rect, R, col, prefix, floors, clad_to):
    """Frame complete, cladding creeping up behind scaffold."""
    objs, _ = _frame(rect, R, col, prefix, floors)
    x0, y0, x1, y1 = rect
    w, d = x1 - x0, y1 - y0
    clad = Part()
    for f in range(clad_to):
        z = BASE_Z + f * FLOOR_H
        for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1),
                                 (x1, y1, x0, y1), (x0, y1, x0, y0)):
            if R.random() > 0.88:                 # a bay still open
                continue
            length = math.hypot(bx - ax, by - ay)
            rot = math.atan2(by - ay, bx - ax)
            clad.box((ax + bx) * 0.5, (ay + by) * 0.5, z + FLOOR_H * 0.5,
                     length * 0.98, 0.18, FLOOR_H * 0.96, rot=rot)
    o = clad.obj(prefix + "_Cladding", "concrete_panel", col)
    if o:
        objs.append(o)
    return objs, (floors + 1) * FLOOR_H


def build_site(name, rect, R, col, stage=None):
    x0, y0, x1, y1 = rect
    w, d = x1 - x0, y1 - y0
    if w < 10.0 or d < 10.0:
        return []
    stage = stage or R.choices(STAGES, weights=STAGE_WEIGHTS, k=1)[0]
    objs = []
    top = 0.0

    if stage == "excavation":
        o, top = _excavation(rect, R, col, name)
    elif stage == "substructure":
        o, top = _substructure(rect, R, col, name)
    elif stage == "frame":
        o, top = _frame(rect, R, col, name, R.randint(2, 7))
    elif stage == "envelope":
        floors = R.randint(4, 9)
        o, top = _envelope(rect, R, col, name, floors, R.randint(1, max(1, floors - 1)))
    else:                                            # fitout
        floors = R.randint(6, 11)
        o, top = _envelope(rect, R, col, name, floors, floors)
    objs.extend(o)

    # scaffold once there is something to scaffold
    if stage in ("frame", "envelope", "fitout") and top > 1.0:
        netted = stage != "fitout"
        margin = 0.9
        objs.extend(_scaffold((x0 - margin, y0 - margin, x1 + margin, y1 + margin),
                              R, col, name + "_Scaffold",
                              min(top, 26.0), netted=netted))

    # the yard around the works
    yard = (x0 - 4.0, y0 - 4.0, x1 + 4.0, y1 + 4.0)
    h = _hoarding(yard, R, col, name + "_Hoarding")
    if h:
        objs.append(h)
    cab = _cabins(x0 - 2.5, y0 - 2.0, R, col, name + "_Cabins", n=R.randint(1, 3))
    if cab:
        objs.append(cab)
    objs.extend(_laydown((x0 - 3.2, y0 - 3.2, x1 + 3.2, y1 + 3.2), R, col, name))

    C.set_asset("construction_last_stage", stage)
    return objs


# -----------------------------------------------------------------------------
def reserve(plan, R, count=None):
    """Pick lots for sites before buildings_types runs, and record them.

    Real cities build everywhere, but not evenly: commercial cores churn
    fastest, residential streets slowest. Candidates are therefore weighted by
    district rather than filtered down to the core, so a large build gets a
    tower crane downtown *and* an infill site out in the neighbourhoods.
    """
    weight_by_district = {
        "downtown": 4.0, "midtown": 3.0, "industrial": 2.5,
        "waterfront": 1.2, "residential": 1.0,
    }
    candidates = []
    for i, b in enumerate(plan["blocks"]):
        if b["district"] == "parkland":
            continue
        if b["w"] < 20.0 or b["h"] < 20.0:
            continue
        candidates.append((i, weight_by_district.get(b["district"], 1.0)))
    if not candidates:
        return set()

    if count is None:
        count = int(round(len(candidates) * 0.18))
        count = max(2, min(count, 8))
    count = min(count, len(candidates))

    chosen = set()
    pool = list(candidates)
    while pool and len(chosen) < count:
        total = sum(w for _, w in pool)
        t = R.uniform(0.0, total)
        acc = 0.0
        for idx, (bi, w) in enumerate(pool):
            acc += w
            if t <= acc:
                chosen.add(bi)
                pool.pop(idx)
                break
        else:
            chosen.add(pool.pop()[0])

    C.set_asset("construction_lots", chosen)
    return chosen


def build():
    R = rng("construction")
    plan = plan_city()
    col = C.col("CITY_Construction")
    _materials()

    lots = C.get_asset("construction_lots", None)
    if not lots:
        lots = reserve(plan, R)

    n_site = 0
    n_obj = 0
    stages = []
    for bi in sorted(lots):
        b = plan["blocks"][bi]
        inset = 6.0
        rect = (b["cx"] - b["w"] * 0.5 + inset, b["cy"] - b["h"] * 0.5 + inset,
                b["cx"] + b["w"] * 0.5 - inset, b["cy"] + b["h"] * 0.5 - inset)
        stage = R.choices(STAGES, weights=STAGE_WEIGHTS, k=1)[0]
        objs = build_site("Site_{:02d}".format(bi), rect, R, col, stage=stage)
        if objs:
            n_site += 1
            n_obj += len(objs)
            stages.append(stage)

    print("  construction: {} sites, {} objects  [{}]".format(
        n_site, n_obj, ", ".join(stages) if stages else "none"))
    return n_site


if __name__ == "__main__":
    C.bootstrap(banner="M22 CONSTRUCTION")
    C.build_all_materials()
    build()
    C.report()
