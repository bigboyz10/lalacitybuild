# =============================================================================
#  CITY BUILD  --  M15 : CAMERAS, TEST RENDERS, GLB EXPORT, REPORT
#  standalone:  blender -b -P render_export.py -- --render --export
# =============================================================================
import bpy
import math
import os
import sys
from mathutils import Vector

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, plan_city

BASE_Z = 0.15


def _camera(name, loc, look_at, lens=35.0, fstop=8.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    direction = Vector(look_at) - Vector(loc)
    ob.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    cd.dof.use_dof = True
    cd.dof.focus_distance = max(1.0, direction.length)
    cd.dof.aperture_fstop = fstop
    C.link_object(ob, C.col("CITY_Cameras"))
    return ob


def build_cameras():
    plan = plan_city()
    half = plan["half"]
    col = C.col("CITY_Cameras")

    # nearest intersection to the centre
    its = sorted(plan["intersections"],
                 key=lambda i: i["x"] ** 2 + i["y"] ** 2)
    it = its[0]
    it2 = its[min(3, len(its) - 1)]

    cams = []
    cams.append(_camera(
        "Cam_Street_A",
        (it["x"] + it["w"] * 0.5 + 1.2, it["y"] - 13.0, BASE_Z + 1.70),
        (it["x"] + it["w"] * 0.5 + 1.2, it["y"] + 45.0, BASE_Z + 2.40),
        lens=32.0, fstop=5.6))

    cams.append(_camera(
        "Cam_Street_B",
        (it2["x"] - it2["w"] * 0.5 - 1.4, it2["y"] + 6.0, BASE_Z + 1.70),
        (it2["x"] - it2["w"] * 0.5 - 1.4, it2["y"] - 40.0, BASE_Z + 2.10),
        lens=50.0, fstop=4.0))

    cams.append(_camera(
        "Cam_Street_C",
        (-half * 0.30, -half + 7.0, BASE_Z + 1.70),
        (-half * 0.10, -half - 40.0, BASE_Z + 1.20),
        lens=24.0, fstop=5.6))

    cams.append(_camera(
        "Cam_Aerial",
        (half * 0.62, -half * 0.86, half * 0.92),
        (0.0, 0.0, 0.0),
        lens=52.0, fstop=11.0))

    C.set_asset("cameras", cams)
    return cams


def render_all():
    sc = bpy.context.scene
    cams = C.get_asset("cameras", [])
    if not cams:
        build_cameras()
        cams = C.get_asset("cameras", [])
    w, h = CONFIG["render_res"]
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    out = CONFIG["out_dir"]
    paths = []
    for cam in cams:
        sc.camera = cam
        path = os.path.join(out, "render_{}.png".format(cam.name))
        sc.render.filepath = path
        print("  rendering {} ...".format(cam.name))
        bpy.ops.render.render(write_still=True)
        paths.append(path)
    return paths


def export_glb():
    path = os.path.join(CONFIG["out_dir"], "city.glb")
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_cameras=False,
        export_lights=False,
        export_yup=True)
    print("  exported {}".format(path))
    return path


def build():
    cams = build_cameras()
    paths = []
    if CONFIG["render"]:
        paths = render_all()
    if CONFIG["export"]:
        export_glb()
    return cams, paths


if __name__ == "__main__":
    C.bootstrap(banner="M15 RENDER / EXPORT")
    C.build_all_materials()
    import terrain, roads, sidewalks, buildings_types
    terrain.build()
    roads.build()
    sidewalks.build()
    buildings_types.build()
    build()
    C.report()