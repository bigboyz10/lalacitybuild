# =============================================================================
#  CITY BUILD  --  M20 : READABLE SIGNAGE
#  Closes critique item 6: "Signage has no readable content. Blades and
#  billboards are coloured slabs; no type, no logos."
#
#  Real extruded type, set in Blender's built-in font and converted to mesh so
#  it survives export to .glb:
#
#    * shop blades and fascias get trade names drawn from a plausible mix of
#      surnames, trades and street-level businesses
#    * billboards get short ad lines sized to the hoarding
#    * intersections get street-name blades on their poles, numbered on the
#      Manhattan convention (numbered streets east-west, named avenues
#      north-south) so the grid reads consistently
#    * entrances get door numbers that increase along each block
#
#  standalone:  blender -b -P signage.py -- --seed 3
# =============================================================================
import math
import os
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, U, rng, plan_city

BASE_Z = 0.15

TRADES = ["PHARMACY", "HARDWARE", "LAUNDROMAT", "BAKERY", "BARBER", "DELI",
          "LIQUOR", "GROCERY", "TAILOR", "LOCKSMITH", "NOTARY", "PAWN",
          "DINER", "NOODLE BAR", "TACOS", "PIZZA", "COFFEE", "BOOKS",
          "RECORDS", "CLEANERS", "OPTICIAN", "FLORIST", "BUTCHER", "SHOE REPAIR"]
SURNAMES = ["OKONKWO", "ROSSI", "NGUYEN", "KOWALSKI", "MERCADO", "HABIB",
            "LINDQVIST", "OYELARAN", "DASILVA", "ABIOLA", "KRISHNAN", "MORENO",
            "ADEYEMI", "PETROV", "YAMADA", "CHUKWU", "BENNETT", "FARUQ"]
PREFIX = ["24H", "THE", "OLD", "NEW", "GOLDEN", "ROYAL", "CORNER", "UNION",
          "LUCKY", "CENTRAL", "FIRST", "METRO"]
AD_LINES = ["EAT MORE FRIES", "FLY DIRECT", "NOW HIRING", "SAVE 40%",
            "OPEN LATE", "CALL 555-0168", "DRINK COLA", "RENT HERE",
            "SUMMER SALE", "NEW SEASON", "TRY THE APP", "LOCAL NEWS"]
AVENUES = ["LEXINGTON", "MADISON", "COLUMBUS", "AMSTERDAM", "HUDSON",
           "ATLANTIC", "PACIFIC", "GRAND", "UNION", "CANAL", "DELANCEY",
           "BOWERY", "ORCHARD", "LUDLOW", "RIVINGTON"]

_FONT = None


def _font():
    global _FONT
    if _FONT is None:
        _FONT = bpy.data.fonts.get("Bfont Regular") or bpy.data.fonts.load("<builtin>")
    return _FONT


def text_mesh(body, name, size=0.5, extrude=0.012, align="CENTER",
              mat="paint_white", collection=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Extruded text converted to a mesh, so it exports and renders anywhere."""
    cu = bpy.data.curves.new(name + "_curve", type="FONT")
    cu.body = body
    cu.font = _font()
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)

    # curve -> mesh so the sign is real geometry, not a font dependency
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    try:
        bpy.ops.object.convert(target="MESH")
    except Exception:
        pass
    ob = bpy.context.view_layer.objects.active
    ob.select_set(False)

    if not ob.data.vertices:
        bpy.data.objects.remove(ob, do_unlink=True)
        return None

    ob.location = loc
    ob.rotation_euler = rot
    if mat:
        ob.data.materials.append(C.M(mat))
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    C.link_object(ob, collection or C.col("CITY_Signage"))
    return ob


def _shop_name(R):
    roll = R.random()
    if roll < 0.34:
        return "{} {}".format(R.choice(SURNAMES), R.choice(["& SONS", "& CO", "BROS"]))
    if roll < 0.68:
        return R.choice(TRADES)
    return "{} {}".format(R.choice(PREFIX), R.choice(TRADES))


def _fit(body, max_w, size):
    """Shrink type until the string fits the board it sits on."""
    approx = len(body) * size * 0.62
    if approx > max_w:
        size *= max_w / approx
    return max(size, 0.06)


def build():
    R = rng("signage")
    plan = plan_city()
    col = C.col("CITY_Signage")
    n_blade = n_board = n_street = n_door = 0

    # ---- lettering on every blade sign ---------------------------------
    for ob in [o for o in bpy.data.objects if o.name.startswith("BladeSign_")]:
        body = _shop_name(R)
        size = _fit(body, 0.92, 0.19)
        loc = ob.location
        # blades project from a facade; face the long axis outward
        for sign_face, yaw in ((1, 0.0), (-1, math.pi)):
            t = text_mesh(
                body, "BladeText_{:04d}".format(n_blade),
                size=size, extrude=0.010, mat="paint_white", collection=col,
                loc=(loc.x, loc.y + 0.05 * sign_face, loc.z),
                rot=(math.pi * 0.5, 0.0, yaw))
            if t:
                n_blade += 1

    # ---- ad copy on billboards -----------------------------------------
    for ob in [o for o in bpy.data.objects if o.name.startswith("BillboardFace_")]:
        body = R.choice(AD_LINES)
        size = _fit(body, 5.2, 0.78)
        loc = ob.location
        t = text_mesh(body, "BillboardText_{:04d}".format(n_board),
                      size=size, extrude=0.02, mat="paint_black", collection=col,
                      loc=(loc.x, loc.y - 0.20, loc.z),
                      rot=(math.pi * 0.5, 0.0, 0.0))
        if t:
            n_board += 1

    # ---- street-name blades at intersections ---------------------------
    half = plan["half"]
    for it in plan["intersections"]:
        if R.random() > 0.65:
            continue
        # numbered streets run east-west, named avenues north-south
        street_no = int(round((it["y"] + half) / 20.0)) + 8
        ew = "{}{} ST".format(street_no, {1: "ST", 2: "ND", 3: "RD"}.get(
            street_no % 10 if street_no % 100 not in (11, 12, 13) else 0, "TH"))
        ns = "{} AVE".format(AVENUES[int(abs(it["x"]) / 25.0) % len(AVENUES)])

        px = it["x"] + it["w"] * 0.5 + 0.35
        py = it["y"] + it["w"] * 0.5 + 0.35
        z = BASE_Z + 3.05

        C.add_cylinder("StreetPole_{:03d}".format(n_street), 0.045, 3.0,
                       loc=(px, py, BASE_Z + 1.5), mat="metal_dark",
                       collection=col)
        for body, yaw, off in ((ew, 0.0, (0.0, 0.18)), (ns, math.pi * 0.5, (0.18, 0.0))):
            size = _fit(body, 0.78, 0.17)
            plate = C.add_box("StreetPlate_{:03d}".format(n_street),
                              (0.90, 0.03, 0.22) if yaw == 0.0 else (0.03, 0.90, 0.22),
                              loc=(px + off[0], py + off[1], z),
                              mat="paint_green", collection=col)
            text_mesh(body, "StreetText_{:03d}".format(n_street),
                      size=size, extrude=0.008, mat="paint_white", collection=col,
                      loc=(px + off[0], py + off[1] - (0.03 if yaw == 0 else 0.0), z),
                      rot=(math.pi * 0.5, 0.0, yaw))
            n_street += 1

    # ---- door numbers ----------------------------------------------------
    for b in C.get_asset("buildings", [])[:220]:
        if not b or R.random() > 0.55:
            continue
        x0, y0, x1, y1 = b["rect"]
        num = abs(int((x0 + y0) * 0.7)) % 900 + 100
        t = text_mesh(str(num), "DoorNum_{:04d}".format(n_door),
                      size=0.17, extrude=0.006, mat="paint_white", collection=col,
                      loc=((x0 + x1) * 0.5 + 0.9, y0 - 0.06, BASE_Z + 2.45),
                      rot=(math.pi * 0.5, 0.0, 0.0))
        if t:
            n_door += 1

    print("  signage: {} shop blades, {} billboards, {} street plates, "
          "{} door numbers".format(n_blade, n_board, n_street, n_door))
    return n_blade + n_board + n_street + n_door


if __name__ == "__main__":
    C.bootstrap(banner="M20 SIGNAGE")
    C.build_all_materials()
    import story
    story.build()
    build()
    C.report()
