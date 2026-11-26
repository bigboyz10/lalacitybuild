# =============================================================================
#  CITY BUILD  --  M14 : LIGHTING & ATMOSPHERE
#  physical sky, sun, street practicals, lit windows, fog, steam, birds
#  standalone:  blender -b -P lighting.py -- --quality preview
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
from buildings_core import BASE_Z, FLOOR_H, GROUND_H, STYLES


def _extra_materials():
    C.make_pbr("steam", base="#dfe4e8", roughness=1.0, bump=0.0,
               var_noise=2, grime=0.0, alpha=0.22)
    C.make_pbr("bird", base="#1a1a1c", roughness=0.9, bump=0.0,
               var_noise=2, grime=0.0)
    C.make_pbr("contrail", base="#e8eef4", roughness=1.0, bump=0.0,
               var_noise=2, grime=0.0, alpha=0.35)


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


def _facades(rect):
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    w, h = x1 - x0, y1 - y0
    return [
        (cx, y0, 1.0, 0.0, 0.0, -1.0, w),
        (cx, y1, 1.0, 0.0, 0.0, 1.0, w),
        (x0, cy, 0.0, 1.0, -1.0, 0.0, h),
        (x1, cy, 0.0, 1.0, 1.0, 0.0, h),
    ]


# -----------------------------------------------------------------------------
def build_world():
    sc = bpy.context.scene
    world = bpy.data.worlds.new("CityWorld")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")

    sky_type = "NISHITA"
    try:
        sky.sky_type = sky_type
    except Exception:
        pass
    for attr, val in (("sun_elevation", math.radians(11.0)),
                      ("sun_rotation", math.radians(215.0)),
                      ("sun_intensity", 0.35),
                      ("altitude", 200.0),
                      ("air_density", 1.4),
                      ("dust_density", 2.2),
                      ("ozone_density", 1.0)):
        try:
            setattr(sky, attr, val)
        except Exception:
            pass

    nt.links.new(sky.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.55
    nt.links.new(bg.outputs[0], out.inputs["Surface"])

    # aerial haze
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.72, 0.78, 0.86, 1.0)
    vol.inputs["Density"].default_value = 0.0035
    try:
        vol.inputs["Anisotropy"].default_value = 0.35
    except Exception:
        pass
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return world


def build_sun():
    sc = bpy.context.scene
    ld = bpy.data.lights.new("Sun", 'SUN')
    ld.energy = 3.2
    ld.color = (1.0, 0.86, 0.68)
    try:
        ld.angle = math.radians(1.2)
    except Exception:
        pass
    ob = bpy.data.objects.new("Sun", ld)
    ob.rotation_euler = (math.radians(74.0), 0.0, math.radians(215.0))
    C.link_object(ob, C.col("CITY_Lighting"))

    ld2 = bpy.data.lights.new("Moon", 'SUN')
    ld2.energy = 0.12
    ld2.color = (0.62, 0.72, 1.0)
    ob2 = bpy.data.objects.new("Moon", ld2)
    ob2.rotation_euler = (math.radians(64.0), 0.0, math.radians(35.0))
    C.link_object(ob2, C.col("CITY_Lighting"))
    return ob


def build_street_lights():
    col = C.col("CITY_Lighting")
    R = rng("lighting")
    plan = plan_city()
    segs = C.get_asset("road_segments", [])
    n = 0
    for s in segs:
        if s["kind"] != "arterial":
            continue
        L = s["b"] - s["a"]
        along = s["a"] + 12.0
        while along < s["b"] - 8.0:
            side = 1 if R.random() < 0.5 else -1
            off = side * (s["w"] * 0.5 + 0.55)
            if s["axis"] == "ns":
                x, y = s["c"] + off, along
            else:
                x, y = along, s["c"] + off
            ld = bpy.data.lights.new("StreetLamp_{:04d}".format(n), 'POINT')
            ld.energy = 900.0
            ld.color = (1.0, 0.80, 0.55)
            ld.shadow_soft_size = 0.35
            ob = bpy.data.objects.new(ld.name, ld)
            ob.location = (x, y, BASE_Z + 8.4)
            C.link_object(ob, col)
            n += 1
            along += 30.0
    return n


def build_lit_windows():
    col = C.col("CITY_Lighting")
    R = rng("litwindows")
    bm_warm = bmesh.new()
    bm_cool = bmesh.new()
    n = 0
    for b in C.get_asset("buildings", []):
        if not b:
            continue
        rect = b["rect"]
        height = b["height"]
        style = b["style"]
        st = STYLES.get(style, STYLES["plaster"])
        floors = max(1, b.get("floors", 1))
        for (px, py, ux, uy, nx, ny, length) in _facades(rect):
            cols = max(1, int(length // st["cols"]))
            step = length / cols
            usable = height - (GROUND_H if floors > 1 else 0.0)
            fl = max(1, int(usable // FLOOR_H))
            for f in range(fl):
                z = BASE_Z + (GROUND_H if floors > 1 else 0.0) + f * FLOOR_H + 1.45
                if z + st["win_h"] * 0.5 > BASE_Z + height - 0.4:
                    continue
                for c in range(cols):
                    if R.random() > 0.16:
                        continue
                    s = -length * 0.5 + step * (c + 0.5)
                    cx = px + ux * s
                    cy = py + uy * s
                    bm = bm_warm if R.random() < 0.7 else bm_cool
                    _vquad(bm, cx, cy, z, ux, uy, nx, ny,
                           st["win_w"] * 0.86, st["win_h"] * 0.86, out=0.055)
                    n += 1
    _mesh("Lights_LitWindows_Warm", bm_warm, "window_warm", col)
    _mesh("Lights_LitWindows_Cool", bm_cool, "window_cool", col)
    return n


def build_steam():
    col = C.col("CITY_Lighting")
    R = rng("steam")
    plan = plan_city()
    n = 0
    for i in range(14):
        b = R.choice(plan["blocks"])
        x = R.uniform(b["x0"] + 2.0, b["x1"] - 2.0)
        y = R.uniform(b["y0"] + 2.0, b["y1"] - 2.0)
        bm = bmesh.new()
        seg = 10
        rings = []
        for k, (zz, rr) in enumerate(((0.0, 0.35), (1.2, 0.55), (2.6, 0.85), (4.0, 1.15))):
            ring = []
            for s in range(seg):
                a = math.tau * s / seg
                ring.append(bm.verts.new((x + rr * math.cos(a),
                                          y + rr * math.sin(a),
                                          BASE_Z + zz)))
            rings.append(ring)
        for k in range(len(rings) - 1):
            a, b2 = rings[k], rings[k + 1]
            for s in range(seg):
                s2 = (s + 1) % seg
                bm.faces.new((a[s], a[s2], b2[s2], b2[s]))
        ob = _mesh("Steam_{:02d}".format(n), bm, "steam", col)
        n += 1
    return n


def build_birds():
    col = C.col("CITY_Lighting")
    R = rng("birds")
    bm = bmesh.new()
    for i in range(26):
        cx = R.uniform(-260, 260)
        cy = R.uniform(-260, 260)
        cz = R.uniform(45, 90)
        s = R.uniform(0.5, 1.1)
        a = R.uniform(0, math.tau)
        ca, sa = math.cos(a), math.sin(a)
        for sgn in (-1, 1):
            p0 = bm.verts.new((cx, cy, cz))
            p1 = bm.verts.new((cx + ca * s * sgn * 1.4 - sa * s * 0.3,
                               cy + sa * s * sgn * 1.4 + ca * s * 0.3,
                               cz + s * 0.25))
            p2 = bm.verts.new((cx + ca * s * sgn * 0.7,
                               cy + sa * s * sgn * 0.7, cz))
            bm.faces.new((p0, p1, p2))
    return _mesh("Atmos_Birds", bm, "bird", col)


def build_aircraft():
    col = C.col("CITY_Lighting")
    R = rng("aircraft")
    bm = bmesh.new()
    cx, cy, cz = R.uniform(-200, 200), R.uniform(120, 220), R.uniform(120, 170)
    ang = R.uniform(0, math.tau)
    ca, sa = math.cos(ang), math.sin(ang)
    body = [bm.verts.new((cx - ca * 6, cy - sa * 6, cz)),
            bm.verts.new((cx + ca * 6, cy + sa * 6, cz)),
            bm.verts.new((cx + ca * 6 - sa * 0.6, cy + sa * 6 + ca * 0.6, cz)),
            bm.verts.new((cx - ca * 6 - sa * 0.6, cy - sa * 6 + ca * 0.6, cz))]
    bm.faces.new(body)
    _mesh("Atmos_Aircraft", bm, "metal_dark", col)

    bm2 = bmesh.new()
    p0 = bm2.verts.new((cx - ca * 6, cy - sa * 6, cz))
    p1 = bm2.verts.new((cx - ca * 90, cy - sa * 90, cz + 1.5))
    p2 = bm2.verts.new((cx - ca * 90 - sa * 1.2, cy - sa * 90 + ca * 1.2, cz + 1.5))
    p3 = bm2.verts.new((cx - ca * 6 - sa * 1.2, cy - sa * 6 + ca * 1.2, cz))
    bm2.faces.new((p0, p1, p2, p3))
    return _mesh("Atmos_Contrail", bm2, "contrail", col)


def build():
    _extra_materials()
    build_world()
    build_sun()
    n_lamps = build_street_lights()
    n_lit = build_lit_windows()
    n_steam = build_steam()
    build_birds()
    build_aircraft()

    sc = bpy.context.scene
    C.set_color_management()
    try:
        sc.view_settings.exposure = 0.55
    except Exception:
        pass
    print("  street lamps: {}  lit windows: {}  steam plumes: {}".format(
        n_lamps, n_lit, n_steam))
    return C.col("CITY_Lighting")


if __name__ == "__main__":
    C.bootstrap(banner="M14 LIGHTING")
    C.build_all_materials()
    import buildings_types
    buildings_types.build()
    build()
    C.report()