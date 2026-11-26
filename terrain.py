# =============================================================================
#  CITY BUILD  --  M1 : TERRAIN, MASTERPLAN GROUND, WATERFRONT, ELEVATED ROAD
#  standalone:  blender -b -P terrain.py -- --quality preview
# =============================================================================
import bpy
import bmesh
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, plan_city, add_box, add_plane, add_grid_surface, add_cylinder, add_rock, rng, fbm


MARGIN = 170.0


# -----------------------------------------------------------------------------
# Terrain height field. Flat and true inside the built area, rolling outside,
# dropping into the river on the south side.
# -----------------------------------------------------------------------------
def ground_z(x, y, half):
    if y < -half:
        t = min(1.0, (-half - y) / 45.0)
        return -2.4 * t * t
    dx = max(0.0, abs(x) - half)
    dy = max(0.0, y - half)
    d = math.hypot(dx, dy)
    if d <= 0.0:
        return 0.0
    t = min(1.0, d / 150.0)
    hills = fbm(x * 0.011, y * 0.011, 4, 7) * 2.2
    ridge = fbm(x * 0.004 + 10.0, y * 0.004, 3, 19) * 9.0
    return (t * t) * (5.0 + ridge) + hills * t


# -----------------------------------------------------------------------------
# Ground shell
# -----------------------------------------------------------------------------
def build_ground(plan, collection):
    half = plan["half"]
    ext = half + MARGIN
    step = 6.0 if CONFIG["quality"] == "preview" else 4.0
    nx = int((2 * ext) / step)
    ny = int((2 * ext) / step)
    obj = add_grid_surface(
        "Terrain_Ground", -ext, ext, -ext, ext, nx, ny,
        lambda x, y: ground_z(x, y, half),
        mat="dirt", collection=collection, smooth=True)
    C.set_asset("ground", obj)
    return obj


def build_block_lots(plan, collection):
    """Flat lot slabs under each block, material chosen by district."""
    R = rng("terrain_lots")
    out = []
    for idx, b in enumerate(plan["blocks"]):
        inset = 0.45
        w = max(1.0, b["w"] - inset * 2)
        h = max(1.0, b["h"] - inset * 2)
        dist = b["district"]
        if dist == "parkland":
            mat = "grass"
        elif dist == "industrial":
            mat = "gravel" if R.random() < 0.6 else "dirt"
        elif dist == "waterfront":
            mat = "concrete_lot"
        else:
            mat = "concrete_lot"
        o = add_plane("Lot_{:03d}_{}".format(idx, dist), (w, h),
                      loc=(b["cx"], b["cy"], 0.006), mat=mat, collection=collection)
        out.append(o)
    return out


# -----------------------------------------------------------------------------
# Waterfront: bulkhead, water, riprap, mooring bollards, embankment kerb
# -----------------------------------------------------------------------------
def build_waterfront(plan, collection):
    half = plan["half"]
    R = rng("terrain_water")
    span = half * 2.0 + 240.0
    wy = -half

    # river surface
    add_plane("Water_River", (span, 260.0),
              loc=(0.0, wy - 130.0, -0.62), mat="water",
              collection=collection, subdiv=24, smooth=True)

    # bulkhead wall (concrete quay)
    add_box("Quay_Bulkhead", (span, 1.30, 2.60),
            loc=(0.0, wy - 0.65, -0.95), mat="concrete",
            collection=collection, bevel=0.03)

    # coping stone on top of the wall
    add_box("Quay_Coping", (span, 1.55, 0.22),
            loc=(0.0, wy - 0.65, 0.40), mat="stone", collection=collection, bevel=0.02)

    # riprap boulders along the water side
    for i in range(70):
        x = R.uniform(-span * 0.5, span * 0.5)
        y = wy - R.uniform(1.8, 7.0)
        z = -0.62 - R.uniform(0.0, 1.4)
        s = R.uniform(0.5, 1.6)
        add_rock("Riprap_{:02d}".format(i), (s * 1.6, s * 1.2, s * 0.8),
                 loc=(x, y, z), rot=(0, 0, R.uniform(0, math.tau)),
                 mat="stone_dark", collection=collection, seed=1000 + i)

    # mooring bollards along the quay
    for i in range(12):
        x = -half + 20.0 + i * (half * 2.0 - 40.0) / 11.0
        add_cylinder("Mooring_Bollard_{:02d}".format(i), 0.22, 0.75,
                     loc=(x, wy - 1.55, 0.52), mat="rust",
                     collection=collection, segments=12)
        add_cylinder("Mooring_Cap_{:02d}".format(i), 0.30, 0.10,
                     loc=(x, wy - 1.55, 0.93), mat="rust",
                     collection=collection, segments=12)

    # ladders down the quay face
    for i in range(4):
        x = -half + 60.0 + i * (half * 2.0 - 120.0) / 3.0
        for r in range(7):
            add_box("Quay_Ladder_{}_{}".format(i, r), (0.06, 0.58, 0.05),
                    loc=(x, wy - 1.35, 0.05 - r * 0.34), mat="metal_dark",
                    collection=collection)
        add_box("Quay_LadderRailL_{}".format(i), (0.05, 0.05, 2.45),
                loc=(x - 0.30, wy - 1.35, -1.05), mat="metal_dark", collection=collection)
        add_box("Quay_LadderRailR_{}".format(i), (0.05, 0.05, 2.45),
                loc=(x + 0.30, wy - 1.35, -1.05), mat="metal_dark", collection=collection)

    # floating pontoon + mooring piles (mid-river)
    add_box("Pontoon", (26.0, 4.0, 0.45), loc=(half * 0.25, wy - 14.0, -0.40),
            mat="wood_pale", collection=collection, bevel=0.02)
    for i in range(4):
        add_cylinder("Pontoon_Pile_{}".format(i), 0.18, 3.2,
                     loc=(half * 0.25 - 12.0 + i * 8.0, wy - 15.9, 0.35),
                     mat="rust", collection=collection, segments=10)

    C.set_asset("water_y", wy)


# -----------------------------------------------------------------------------
# Elevated highway on the north edge: deck, piers, barriers, joints, markings
# -----------------------------------------------------------------------------
def build_highway(plan, collection):
    half = plan["half"]
    hy = plan["highway_y"]
    deck_top = 9.0
    deck_t = 1.10
    width = 21.0
    length = half * 2.0 + 260.0
    x0 = -length * 0.5

    add_box("Highway_Deck", (length, width, deck_t),
            loc=(0.0, hy, deck_top - deck_t * 0.5), mat="asphalt",
            collection=collection, bevel=0.04)

    # fascia beams
    for s in (-1, 1):
        add_box("Highway_Fascia_{}".format("N" if s > 0 else "S"),
                (length, 0.45, 0.85),
                loc=(0.0, hy + s * (width * 0.5 - 0.10), deck_top - 0.55),
                mat="concrete", collection=collection, bevel=0.02)

    # concrete barriers
    for s in (-1, 1):
        add_box("Highway_Barrier_{}".format("N" if s > 0 else "S"),
                (length, 0.55, 1.05),
                loc=(0.0, hy + s * (width * 0.5 - 0.55), deck_top + 0.52),
                mat="concrete", collection=collection, bevel=0.04)

    # lamp masts on the median barrier line
    for i in range(14):
        x = x0 + 30.0 + i * (length - 60.0) / 13.0
        add_cylinder("Highway_Mast_{:02d}".format(i), 0.12, 8.0,
                     loc=(x, hy + width * 0.5 - 1.2, deck_top + 4.0),
                     mat="metal_galv", collection=collection, segments=10)
        add_box("Highway_MastArm_{:02d}".format(i), (2.1, 0.14, 0.14),
                loc=(x - 1.0, hy + width * 0.5 - 1.2, deck_top + 8.0),
                mat="metal_galv", collection=collection)
        add_box("Highway_MastHead_{:02d}".format(i), (0.75, 0.30, 0.16),
                loc=(x - 2.0, hy + width * 0.5 - 1.2, deck_top + 7.95),
                mat="metal_dark", collection=collection)

    # piers + cap beams
    pier_x = x0 + 22.0
    idx = 0
    while pier_x < -x0 - 22.0:
        gz = ground_z(pier_x, hy, half)
        pier_h = (deck_top - deck_t) - gz
        if pier_h > 0.8:
            add_box("Highway_Pier_{:03d}".format(idx), (1.8, 3.0, pier_h),
                    loc=(pier_x, hy, gz + pier_h * 0.5), mat="concrete",
                    collection=collection, bevel=0.05)
            add_box("Highway_PierCap_{:03d}".format(idx), (2.4, width - 2.0, 0.65),
                    loc=(pier_x, hy, deck_top - deck_t - 0.33), mat="concrete",
                    collection=collection, bevel=0.04)
            add_box("Highway_PierFoot_{:03d}".format(idx), (3.2, 4.4, 0.55),
                    loc=(pier_x, hy, gz + 0.27), mat="concrete",
                    collection=collection, bevel=0.05)
        pier_x += 26.0
        idx += 1

    # expansion joints across the deck
    j = 0
    jx = x0 + 12.0
    while jx < -x0 - 12.0:
        add_box("Highway_Joint_{:02d}".format(j), (0.22, width - 1.2, 0.06),
                loc=(jx, hy, deck_top + 0.01), mat="metal_dark", collection=collection)
        jx += 12.0
        j += 1

    # lane markings: dashed white between 4 lanes, solid edge lines
    for lane_y in (-5.25, 5.25):
        d = 0
        dx = x0 + 6.0
        while dx < -x0 - 6.0:
            add_plane("Highway_Dash_{}_{:03d}".format("N" if lane_y > 0 else "S", d),
                      (3.0, 0.15), loc=(dx, hy + lane_y, deck_top + 0.012),
                      mat="paint_white", collection=collection)
            dx += 9.0
            d += 1
    for edge_y in (-width * 0.5 + 1.1, width * 0.5 - 1.1):
        add_plane("Highway_EdgeLine_{}".format("N" if edge_y > 0 else "S"),
                  (length - 4.0, 0.20), loc=(0.0, hy + edge_y, deck_top + 0.012),
                  mat="paint_white", collection=collection)

    # guard rail posts along the outer fascia (visible from street)
    for i in range(int(length / 3.0)):
        x = x0 + i * 3.0
        add_box("Highway_Post_{:03d}".format(i), (0.10, 0.10, 0.75),
                loc=(x, hy - width * 0.5 - 0.12, deck_top + 0.37),
                mat="metal_galv", collection=collection)

    C.set_asset("highway_y", hy)
    C.set_asset("highway_deck_z", deck_top)


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
def build():
    plan = plan_city()
    collection = C.col("CITY_Terrain")
    build_ground(plan, collection)
    build_block_lots(plan, collection)
    build_waterfront(plan, collection)
    build_highway(plan, collection)
    return plan


if __name__ == "__main__":
    C.bootstrap(banner="M1 TERRAIN")
    C.build_all_materials()
    p = build()
    C.report()
    print("  terrain built: {} blocks, river at y={:.1f}, highway at y={:.1f}".format(
        len(p["blocks"]), p["water_y"], p["highway_y"]))
