# =============================================================================
#  CITY BUILD  --  TEXTURED PBR ASSETS
#  Upgrades the procedural material library with real photographic CC0 PBR
#  texture sets (Poly Haven) and an HDRI sky, when those files are present.
#
#  Download them first:   python3 tools/fetch_assets.py --res 2k
#  Then every build picks them up automatically; with no files on disk the
#  original procedural materials are used unchanged, so this is purely additive.
# =============================================================================
import os
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG

TEX_DIR = os.path.join(_HERE, "assets", "textures")
HDRI_DIR = os.path.join(_HERE, "assets", "hdri")

# city material name -> (texture set, UV scale in metres per tile)
BINDINGS = {
    "asphalt":         ("asphalt", 6.0),
    "asphalt_worn":    ("asphalt_worn", 7.0),
    "road":            ("asphalt", 6.0),
    "concrete":        ("concrete", 4.0),
    "concrete_panel":  ("concrete_wall", 5.0),
    "sidewalk":        ("pavement", 2.4),
    "pavement":        ("pavement", 2.4),
    "brick_old":       ("brick_old", 3.0),
    "brick_modern":    ("brick_modern", 3.2),
    "plaster":         ("plaster", 4.5),
    "stone_old":       ("stone_old", 3.6),
    "metal_dark":      ("metal_dark", 2.0),
    "metal_rust":      ("rust", 2.2),
    "rust":            ("rust", 2.2),
    "roof_tar":        ("roof_tar", 3.0),
    "grass":           ("grass", 8.0),
    "tiles_floor":     ("tiles_floor", 2.0),
}

_IMG_CACHE = {}


def available():
    """True when at least one downloaded texture set is on disk."""
    return os.path.isdir(TEX_DIR) and any(
        os.path.isdir(os.path.join(TEX_DIR, d)) for d in os.listdir(TEX_DIR)
    ) if os.path.isdir(TEX_DIR) else False


def _find(set_name, kind):
    folder = os.path.join(TEX_DIR, set_name)
    if not os.path.isdir(folder):
        return None
    for ext in (".jpg", ".png", ".jpeg"):
        path = os.path.join(folder, kind + ext)
        if os.path.exists(path):
            return path
    return None


def _image(path, non_color):
    key = (path, non_color)
    if key in _IMG_CACHE:
        return _IMG_CACHE[key]
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    _IMG_CACHE[key] = img
    return img


def build_textured_material(mat_name, set_name, scale):
    """Replace a material's node tree with a photographic PBR setup."""
    diffuse = _find(set_name, "diffuse")
    if diffuse is None:
        return None

    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (560, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])

    coord = nt.nodes.new("ShaderNodeTexCoord"); coord.location = (-900, 0)
    mapping = nt.nodes.new("ShaderNodeMapping"); mapping.location = (-700, 0)
    mapping.inputs["Scale"].default_value = (1.0 / scale, 1.0 / scale, 1.0 / scale)
    # object coordinates keep tiling consistent across the whole city
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])

    def tex(path, non_color, loc):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = _image(path, non_color)
        node.location = loc
        node.projection = "BOX"
        node.projection_blend = 0.25
        node.extension = "REPEAT"
        nt.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node

    col = tex(diffuse, False, (-400, 260))

    ao_path = _find(set_name, "ao")
    if ao_path:
        ao = tex(ao_path, True, (-400, 500))
        mix = nt.nodes.new("ShaderNodeMix"); mix.location = (160, 300)
        mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 0.65
        nt.links.new(col.outputs["Color"], mix.inputs[6])
        nt.links.new(ao.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    else:
        nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])

    rough_path = _find(set_name, "roughness")
    if rough_path:
        rough = tex(rough_path, True, (-400, 0))
        nt.links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.65

    nor_path = _find(set_name, "normal")
    if nor_path:
        nor = tex(nor_path, True, (-400, -260))
        nmap = nt.nodes.new("ShaderNodeNormalMap"); nmap.location = (160, -260)
        nmap.inputs["Strength"].default_value = 1.0
        nt.links.new(nor.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    disp_path = _find(set_name, "displacement")
    if disp_path and CONFIG.get("quality") == "high":
        disp_tex = tex(disp_path, True, (-400, -520))
        disp = nt.nodes.new("ShaderNodeDisplacement"); disp.location = (560, -400)
        disp.inputs["Scale"].default_value = 0.02
        nt.links.new(disp_tex.outputs["Color"], disp.inputs["Height"])
        nt.links.new(disp.outputs["Displacement"], out.inputs["Displacement"])

    C.MATS[mat_name] = mat
    return mat


def build_world_hdri(strength=1.0):
    """Light the city with a real captured sky if an HDRI is on disk."""
    if not os.path.isdir(HDRI_DIR):
        return None
    hdrs = [f for f in sorted(os.listdir(HDRI_DIR)) if f.lower().endswith((".hdr", ".exr"))]
    if not hdrs:
        return None
    path = os.path.join(HDRI_DIR, hdrs[0])

    world = bpy.context.scene.world or bpy.data.worlds.new("CityWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (600, 0)
    bg = nt.nodes.new("ShaderNodeBackground"); bg.location = (380, 0)
    bg.inputs["Strength"].default_value = strength
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.location = (80, 0)
    env.image = bpy.data.images.load(path, check_existing=True)
    mapping = nt.nodes.new("ShaderNodeMapping"); mapping.location = (-160, 0)
    coord = nt.nodes.new("ShaderNodeTexCoord"); coord.location = (-360, 0)
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    print("  HDRI sky: {}".format(os.path.basename(path)))
    return world


def build():
    if not available():
        print("  no downloaded textures found - keeping procedural materials")
        print("  run: python3 tools/fetch_assets.py --res 2k")
        return 0
    n = 0
    for mat_name, (set_name, scale) in BINDINGS.items():
        if build_textured_material(mat_name, set_name, scale):
            n += 1
    build_world_hdri()
    print("  upgraded {} materials to photographic PBR".format(n))
    return n


if __name__ == "__main__":
    C.bootstrap(banner="TEXTURED PBR ASSETS")
    C.build_all_materials()
    build()
