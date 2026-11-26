# =============================================================================
#  CITY BUILD  --  M7 : ROOFS & ROOFTOP EQUIPMENT
#  standalone:  blender -b -P roofs.py -- --quality preview
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
from core import CONFIG, U, rng, add_box, add_cylinder, add_plane, add_rock
from buildings_core import BASE_Z, STYLES


def _roof_z(b):
    return BASE_Z + b["height"]


def build():
    collection = C.col("CITY_Roofs")
    R = rng("roofs")
    buildings = [b for b in C.get_asset("buildings", []) if b]
    detail = 1.0 if CONFIG["quality"] == "high" else 0.6

    n_hvac = n_tank = n_ant = n_solar = n_hatch = 0

    for b in buildings:
        x0, y0, x1, y1 = b["rect"]
        w, h = x1 - x0, y1 - y0
        if w < 5.0 or h < 5.0:
            continue
        z = _roof_z(b)
        style = b["style"]
        st = STYLES.get(style, STYLES["plaster"])
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5

        # roof deck
        add_plane("{}_RoofDeck".format(b["name"]), (w - 0.5, h - 0.5),
                  loc=(cx, cy, z + 0.02),
                  mat="gravel" if R.random() < 0.5 else "asphalt_patch",
                  collection=collection)

        # stair / lift bulkhead
        if R.random() < 0.7 and w > 7.0 and h > 7.0:
            bw = min(4.0, w * 0.3)
            bh = min(3.6, h * 0.3)
            add_box("{}_Bulkhead".format(b["name"]), (bw, bh, 2.6),
                    loc=(x0 + bw * 0.5 + 1.2, y0 + bh * 0.5 + 1.2, z + 1.3),
                    mat=st["wall"], collection=collection, bevel=0.03)
            add_box("{}_BulkheadDoor".format(b["name"]), (1.0, 0.12, 2.1),
                    loc=(x0 + bw * 0.5 + 1.2, y0 + 1.2 - 0.02, z + 1.05),
                    mat="metal_dark", collection=collection)
            n_hatch += 1

        # HVAC packaged units
        n = R.randint(1, 3) if w * h > 120 else 1
        for i in range(n):
            if R.random() > detail:
                continue
            ux = R.uniform(x0 + 2.0, x1 - 2.0)
            uy = R.uniform(y0 + 2.0, y1 - 2.0)
            add_box("{}_HVAC{}".format(b["name"], i), (2.4, 1.6, 1.1),
                    loc=(ux, uy, z + 0.55), mat="metal_galv",
                    collection=collection, bevel=0.03)
            add_cylinder("{}_HVACFan{}".format(b["name"], i), 0.52, 0.10,
                         loc=(ux, uy, z + 1.12), mat="metal_dark",
                         collection=collection, segments=14)
            n_hvac += 1

        # vents / exhaust stacks
        for i in range(R.randint(1, 4)):
            vx = R.uniform(x0 + 1.5, x1 - 1.5)
            vy = R.uniform(y0 + 1.5, y1 - 1.5)
            add_cylinder("{}_Vent{}".format(b["name"], i), 0.16, 1.2,
                         loc=(vx, vy, z + 0.6), mat="metal_galv",
                         collection=collection, segments=8)
            add_cylinder("{}_VentCap{}".format(b["name"], i), 0.26, 0.10,
                         loc=(vx, vy, z + 1.22), mat="metal_dark",
                         collection=collection, segments=8)

        # brick chimney on masonry buildings
        if style in ("brick_old", "stone_old", "brick_modern") and R.random() < 0.55:
            chx = R.uniform(x0 + 1.5, x1 - 1.5)
            chy = R.uniform(y0 + 1.5, y1 - 1.5)
            add_box("{}_Chimney".format(b["name"]), (1.1, 1.1, 2.8),
                    loc=(chx, chy, z + 1.4), mat="brick_dark",
                    collection=collection, bevel=0.02)
            add_box("{}_ChimneyCap".format(b["name"]), (1.35, 1.35, 0.16),
                    loc=(chx, chy, z + 2.86), mat="stone_dark",
                    collection=collection)

        # wooden water tank on steel legs
        if (style in ("brick_old", "stone_old", "plaster", "plaster_pink")
                and w > 9.0 and h > 9.0 and R.random() < 0.35):
            tx = R.uniform(x0 + 3.0, x1 - 3.0)
            ty = R.uniform(y0 + 3.0, y1 - 3.0)
            leg_h = 2.4
            for sx in (-1, 1):
                for sy in (-1, 1):
                    add_box("{}_TankLeg{}{}".format(b["name"], sx, sy),
                            (0.16, 0.16, leg_h),
                            loc=(tx + sx * 1.1, ty + sy * 1.1, z + leg_h * 0.5),
                            mat="metal_dark", collection=collection)
            add_cylinder("{}_Tank".format(b["name"]), 1.55, 2.6,
                         loc=(tx, ty, z + leg_h + 1.3), mat="wood",
                         collection=collection, segments=18)
            add_cylinder("{}_TankTop".format(b["name"]), 1.55, 0.9,
                         loc=(tx, ty, z + leg_h + 3.05), mat="wood_pale",
                         collection=collection, segments=18, radius_top=0.12)
            for k in range(2):
                add_cylinder("{}_TankHoop{}".format(b["name"], k), 1.60, 0.07,
                             loc=(tx, ty, z + leg_h + 0.7 + k * 1.2),
                             mat="rust", collection=collection, segments=18)
            n_tank += 1

        # antennas
        if R.random() < 0.45:
            ax = R.uniform(x0 + 1.5, x1 - 1.5)
            ay = R.uniform(y0 + 1.5, y1 - 1.5)
            ah = R.uniform(3.0, 7.0)
            add_cylinder("{}_Antenna".format(b["name"]), 0.05, ah,
                         loc=(ax, ay, z + ah * 0.5), mat="metal_galv",
                         collection=collection, segments=6)
            for k in range(3):
                add_box("{}_AntennaBar{}".format(b["name"], k), (1.4, 0.04, 0.04),
                        loc=(ax, ay, z + ah * (0.45 + k * 0.18)),
                        mat="metal_galv", collection=collection)
            n_ant += 1

        # satellite dish
        if R.random() < 0.3:
            dx = R.uniform(x0 + 1.5, x1 - 1.5)
            dy = R.uniform(y0 + 1.5, y1 - 1.5)
            add_cylinder("{}_Dish".format(b["name"]), 0.55, 0.10,
                         loc=(dx, dy, z + 1.2),
                         rot=(math.radians(55), 0.0, R.uniform(0, math.tau)),
                         mat="metal_galv", collection=collection, segments=14)
            add_box("{}_DishArm".format(b["name"]), (0.08, 0.08, 1.2),
                    loc=(dx, dy, z + 0.6), mat="metal_dark", collection=collection)

        # skylights
        if R.random() < 0.35 and w > 8.0 and h > 8.0:
            sx = R.uniform(x0 + 2.5, x1 - 2.5)
            sy = R.uniform(y0 + 2.5, y1 - 2.5)
            add_box("{}_SkylightFrame".format(b["name"]), (2.2, 1.4, 0.28),
                    loc=(sx, sy, z + 0.16), mat="metal_dark",
                    collection=collection, bevel=0.02)
            add_plane("{}_SkylightGlass".format(b["name"]), (2.0, 1.2),
                      loc=(sx, sy, z + 0.31), mat="glass_dirty",
                      collection=collection)

        # solar panels
        if R.random() < 0.22 and w > 9.0 and h > 9.0:
            for i in range(R.randint(2, 5)):
                px = R.uniform(x0 + 2.0, x1 - 2.0)
                py = R.uniform(y0 + 2.0, y1 - 2.0)
                add_box("{}_Solar{}".format(b["name"], i), (2.4, 1.2, 0.06),
                        loc=(px, py, z + 0.55),
                        rot=(math.radians(-26), 0.0, R.uniform(-0.3, 0.3)),
                        mat="glass_dark", collection=collection)
                n_solar += 1

        # helipad on the tall towers
        if b["height"] > 55.0 and w > 16.0 and h > 16.0:
            add_cylinder("{}_Helipad".format(b["name"]), min(w, h) * 0.32, 0.06,
                         loc=(cx, cy, z + 0.06), mat="asphalt",
                         collection=collection, segments=28)
            for k, (ox, oy, sx, sy) in enumerate([(-1.6, 0, 0.5, 4.4),
                                                  (1.6, 0, 0.5, 4.4),
                                                  (0, 0, 3.0, 0.5)]):
                add_plane("{}_HelipadMark{}".format(b["name"], k), (sx, sy),
                          loc=(cx + ox, cy + oy, z + 0.10),
                          mat="paint_white", collection=collection)

    print("  roofs: {}  hvac: {}  tanks: {}  antennas: {}  solar: {}  hatches: {}".format(
        len(buildings), n_hvac, n_tank, n_ant, n_solar, n_hatch))
    return collection


if __name__ == "__main__":
    C.bootstrap(banner="M7 ROOFS")
    C.build_all_materials()
    import buildings_types
    buildings_types.build()
    build()
    C.report()