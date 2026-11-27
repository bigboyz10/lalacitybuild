# =============================================================================
#  CITY BUILD  --  M0 : CORE FRAMEWORK
#  Blender 4.x   |   headless:   blender -b -P core.py -- --quality preview
#
#  Everything the other modules share: CONFIG, deterministic RNG streams,
#  collections, the procedural material library, geometry helpers, the city
#  masterplan solver and the reporting pass.
# =============================================================================
import bpy
import bmesh
import math
import random
import hashlib
import sys
import os
import json
from mathutils import Vector, Matrix

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# -----------------------------------------------------------------------------
# CONFIG  (single source of truth, every module reads this)
# -----------------------------------------------------------------------------
CONFIG = {
    "seed": 1337,
    "city_size": 900.0,       # metres, square footprint of the built city
    "density": 0.85,          # 0..1, fraction of lots that get buildings
    "quality": "preview",     # "preview" (EEVEE) | "high" (Cycles)
    "render": False,          # render the 4 test frames
    "export": False,          # write city.glb
    "only": [],               # module whitelist for partial rebuilds
    "out_dir": _HERE,
    "samples_preview": 48,
    "samples_high": 320,
    "render_res": (1280, 720),
    "band_lod": True,
    "save_blend": True,       # write city.blend at the end of a master run
    "blend_name": "city.blend",
    "textures": True,         # use downloaded photographic PBR when available
    "engine": "auto",         # auto | eevee | cycles  (auto -> cycles headless)
    "samples_render": 64,     # cycles samples for a normal --render pass
    "look": "la",             # la (Los Angeles) | nyc (the original dense, dark city)
    "time": None,             # day | golden | night ; None -> day for la, night for nyc
    "damage": False,          # LA look skips the decay/boarded-up pass unless asked
}

# real-world unit constants (metres)
U = {
    "lane": 3.0,
    "curb": 0.15,
    "curb_depth": 0.20,
    "door_w": 1.05,
    "door_h": 2.10,
    "floor_h": 3.40,
    "eye": 1.70,
    "sidewalk": 3.20,
    "paint_h": 0.006,
    "mintick": 0.001,
}

ASSETS = {}        # name -> bpy object (cross module registry)
MATS = {}          # name -> bpy material
CITY_PLAN = {}     # solved masterplan

ROOT_COL = "CITY"


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def parse_argv():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    i = 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        if a == "--seed" and nxt is not None:
            CONFIG["seed"] = int(nxt); i += 2
        elif a == "--size" and nxt is not None:
            CONFIG["city_size"] = float(nxt); i += 2
        elif a == "--density" and nxt is not None:
            CONFIG["density"] = float(nxt); i += 2
        elif a == "--quality" and nxt is not None:
            CONFIG["quality"] = nxt; i += 2
        elif a == "--out" and nxt is not None:
            CONFIG["out_dir"] = os.path.abspath(nxt); i += 2
        elif a == "--only" and nxt is not None:
            CONFIG["only"] = [s.strip() for s in nxt.split(",") if s.strip()]; i += 2
        elif a == "--export":
            CONFIG["export"] = True; i += 1
        elif a == "--render":
            CONFIG["render"] = True; i += 1
        elif a == "--no-render":
            CONFIG["render"] = False; i += 1
        elif a == "--no-lod":
            CONFIG["band_lod"] = False; i += 1
        elif a == "--blend" and nxt is not None:
            CONFIG["blend_name"] = nxt; CONFIG["save_blend"] = True; i += 2
        elif a == "--no-blend":
            CONFIG["save_blend"] = False; i += 1
        elif a == "--no-textures":
            CONFIG["textures"] = False; i += 1
        elif a == "--engine" and nxt is not None:
            CONFIG["engine"] = nxt.lower(); i += 2
        elif a == "--samples" and nxt is not None:
            CONFIG["samples_render"] = int(nxt); i += 2
        elif a == "--look" and nxt is not None:
            CONFIG["look"] = nxt.lower(); i += 2
        elif a == "--time" and nxt is not None:
            CONFIG["time"] = nxt.lower(); i += 2
        elif a == "--damage":
            CONFIG["damage"] = True; i += 1
        else:
            i += 1
    os.makedirs(CONFIG["out_dir"], exist_ok=True)
    return CONFIG


def is_la():
    """True when the Los Angeles look is active (the default)."""
    return CONFIG.get("look", "la") == "la"


def la_palm_slot(x, y):
    """Deterministic ~55% of street-tree slots become palms in the LA look.

    Both trees.py (which skips those slots) and la_style.py (which fills them)
    call this, so the two modules never need to talk to each other.
    """
    h = (int(round(x * 2.0)) * 73856093) ^ (int(round(y * 2.0)) * 19349663)
    return (h & 0xFFFF) % 100 < 55


def wants(module_key):
    """True when this module should run (honours --only)."""
    return (not CONFIG["only"]) or (module_key in CONFIG["only"])


# -----------------------------------------------------------------------------
# Deterministic RNG -- one independent stream per module name
# -----------------------------------------------------------------------------
def rng(name):
    raw = "{}:{}".format(CONFIG["seed"], name).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return random.Random(int(digest[:16], 16))


def seeded(name):
    return rng(name)


# -----------------------------------------------------------------------------
# Value noise (dependency free, deterministic)
# -----------------------------------------------------------------------------
def _h2(ix, iy, seed):
    n = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) & 0xFFFFFFFF
    n = (n * 1274126177) & 0xFFFFFFFF
    n = (n ^ (n >> 16)) & 0xFFFFFFFF
    return n / 4294967295.0


def vnoise(x, y, seed=0):
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    a = _h2(ix, iy, seed)
    b = _h2(ix + 1, iy, seed)
    c = _h2(ix, iy + 1, seed)
    d = _h2(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm(x, y, octaves=4, seed=0):
    total = 0.0
    amp = 0.5
    freq = 1.0
    norm = 0.0
    for i in range(octaves):
        total += amp * vnoise(x * freq, y * freq, seed + i * 31)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm if norm else 0.0


# -----------------------------------------------------------------------------
# Scene bootstrap
# -----------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_units():
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = "METERS"


def set_engine(quality=None):
    """Pick a render engine.

    EEVEE needs a real GPU; headless Blender falls back to the llvmpipe
    software rasteriser where it is slower than Cycles by a wide margin. So
    "auto" uses Cycles on CPU whenever we are actually going to render, and
    only keeps EEVEE for build-only runs where the engine never executes.
    """
    sc = bpy.context.scene
    q = quality or CONFIG["quality"]
    want = CONFIG.get("engine", "auto")

    if want == "auto":
        use_cycles = (q == "high") or bool(CONFIG.get("render"))
    else:
        use_cycles = (want == "cycles")

    if use_cycles:
        sc.render.engine = "CYCLES"
        try:
            sc.cycles.samples = (CONFIG["samples_high"] if q == "high"
                                 else CONFIG["samples_render"])
            sc.cycles.use_denoising = True
            sc.cycles.device = "CPU"
            sc.cycles.max_bounces = 8 if q == "high" else 4
            sc.cycles.caustics_reflective = False
            sc.cycles.caustics_refractive = False
            sc.cycles.use_fast_gi = q != "high"
        except Exception:
            pass
        return

    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = engine
            break
        except TypeError:
            continue
    try:
        sc.eevee.taa_render_samples = CONFIG["samples_preview"]
    except Exception:
        pass
    for attr, val in (("use_gtao", True), ("use_volumetric_lights", True),
                      ("use_raytracing", True)):
        try:
            setattr(sc.eevee, attr, val)
        except Exception:
            pass


def set_color_management():
    sc = bpy.context.scene
    try:
        sc.view_settings.view_transform = "AgX"
    except Exception:
        pass
    for look in ("AgX - Medium High Contrast", "AgX - Base Contrast", "None"):
        try:
            sc.view_settings.look = look
            break
        except Exception:
            continue
    sc.view_settings.exposure = 0.35
    try:
        sc.render.image_settings.file_format = "PNG"
        sc.render.film_transparent = False
    except Exception:
        pass


def bootstrap(reset=True, engine=True, banner="CITY BUILD"):
    parse_argv()
    if reset:
        reset_scene()
    setup_units()
    ensure_collection(ROOT_COL)
    ensure_collection("CITY_LOD", ROOT_COL)
    if engine:
        set_engine()
        set_color_management()
    print("\n" + "=" * 78)
    print(" {}  |  seed={}  size={}m  density={}  quality={}".format(
        banner, CONFIG["seed"], CONFIG["city_size"], CONFIG["density"], CONFIG["quality"]))
    print("=" * 78)
    return CONFIG


# -----------------------------------------------------------------------------
# Collections
# -----------------------------------------------------------------------------
def ensure_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is not None:
        return col
    col = bpy.data.collections.new(name)
    if parent is None:
        bpy.context.scene.collection.children.link(col)
    else:
        p = ensure_collection(parent) if isinstance(parent, str) else parent
        p.children.link(col)
    return col


def link_object(obj, collection):
    col = collection if isinstance(collection, bpy.types.Collection) else ensure_collection(collection)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def col(name):
    return ensure_collection(name, ROOT_COL)


def ensure_lod_collections(base, parent="CITY_LOD"):
    out = {}
    p = ensure_collection(parent, ROOT_COL)
    for tier in range(4):
        out[tier] = ensure_collection("{}_LOD{}".format(base, tier), p)
    return out


def move_to_lod(obj, base, tier=0):
    lods = ensure_lod_collections(base)
    link_object(obj, lods[max(0, min(3, tier))])
    return obj


def get_asset(name, default=None):
    return ASSETS.get(name, default)


def set_asset(name, obj):
    ASSETS[name] = obj
    return obj


# -----------------------------------------------------------------------------
# Colour helpers
# -----------------------------------------------------------------------------
def _lin(c):
    c = max(0.0, min(1.0, c))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexc(h, mul=1.0, alpha=1.0):
    h = h.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (_lin(r * mul), _lin(g * mul), _lin(b * mul), alpha)


def shade(c, f):
    return (max(0.0, min(1.0, c[0] * f)),
            max(0.0, min(1.0, c[1] * f)),
            max(0.0, min(1.0, c[2] * f)),
            1.0)


def _setin(node, name, value):
    if name in node.inputs:
        try:
            node.inputs[name].default_value = value
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Procedural PBR material library
# -----------------------------------------------------------------------------
PALETTE = {
    # ground / roads
    "asphalt":        dict(base="#3b3b3d", roughness=0.93, bump=0.45, bump_scale=11, var_noise=5, grime=0.5, grime_tint=0.55),
    "asphalt_patch":  dict(base="#2c2c2e", roughness=0.96, bump=0.35, bump_scale=9, var_noise=7, grime=0.4),
    "asphalt_wet":    dict(base="#2a2b2d", roughness=0.35, bump=0.30, bump_scale=9, var_noise=5, grime=0.4),
    "concrete":       dict(base="#9b968f", roughness=0.86, bump=0.30, bump_scale=13, var_noise=4, grime=0.55, grime_tint=0.62),
    "concrete_lot":   dict(base="#8b867f", roughness=0.90, bump=0.26, bump_scale=8, var_noise=3, grime=0.6),
    "curb":           dict(base="#8f8a83", roughness=0.88, bump=0.30, bump_scale=15, var_noise=5, grime=0.5),
    "paint_black":    dict(base="#141414", roughness=0.74, bump=0.10, var_noise=5, grime=0.30),
    "paint_white":    dict(base="#d8d4ca", roughness=0.80, bump=0.10, var_noise=6, grime=0.35),
    "paint_yellow":   dict(base="#d6ae35", roughness=0.80, bump=0.10, var_noise=6, grime=0.35),
    "paint_green":    dict(base="#2f6b45", roughness=0.82, bump=0.10, var_noise=6, grime=0.4),
    "paint_red":      dict(base="#8d2f2c", roughness=0.85, bump=0.10, var_noise=6, grime=0.4),
    # masonry
    "brick":          dict(base="#7c3d2f", roughness=0.88, bump=0.50, bump_scale=22, var_noise=9, grime=0.5),
    "brick_dark":     dict(base="#5c2d24", roughness=0.90, bump=0.50, bump_scale=22, var_noise=9, grime=0.5),
    "brick_pale":     dict(base="#a8795f", roughness=0.86, bump=0.45, bump_scale=22, var_noise=9, grime=0.45),
    "stone":          dict(base="#a49d92", roughness=0.82, bump=0.42, bump_scale=16, var_noise=6, grime=0.55),
    "stone_dark":     dict(base="#6f6a62", roughness=0.84, bump=0.42, bump_scale=16, var_noise=6, grime=0.5),
    "plaster":        dict(base="#c8c1b1", roughness=0.88, bump=0.22, bump_scale=12, var_noise=5, grime=0.5),
    "plaster_pink":   dict(base="#c09a8d", roughness=0.88, bump=0.22, bump_scale=12, var_noise=5, grime=0.5),
    "plaster_teal":   dict(base="#7f9a96", roughness=0.88, bump=0.22, bump_scale=12, var_noise=5, grime=0.5),
    # --- Los Angeles palette: sun-bleached stucco, terracotta tile, palms ---
    "stucco_cream":   dict(base="#dccaa2", roughness=0.93, bump=0.38, bump_scale=34, var_noise=6, grime=0.22),
    "stucco_peach":   dict(base="#dba98a", roughness=0.93, bump=0.38, bump_scale=34, var_noise=6, grime=0.22),
    "stucco_white":   dict(base="#e6e2d6", roughness=0.92, bump=0.36, bump_scale=34, var_noise=5, grime=0.20),
    "stucco_terracotta": dict(base="#b96a4c", roughness=0.93, bump=0.38, bump_scale=34, var_noise=6, grime=0.22),
    "stucco_sage":    dict(base="#a9b39a", roughness=0.93, bump=0.38, bump_scale=34, var_noise=6, grime=0.22),
    "stucco_sky":     dict(base="#9fbac6", roughness=0.93, bump=0.38, bump_scale=34, var_noise=6, grime=0.22),
    "stucco_butter":  dict(base="#e3d08f", roughness=0.93, bump=0.38, bump_scale=34, var_noise=6, grime=0.22),
    "trim_white":     dict(base="#ece8de", roughness=0.70, bump=0.10, var_noise=3, grime=0.15),
    "roof_tile":      dict(base="#a8553a", roughness=0.75, bump=0.55, bump_scale=44, var_noise=8, grime=0.3),
    "palm_bark":      dict(base="#7b6a55", roughness=0.95, bump=0.85, bump_scale=22, var_noise=10, grime=0.3),
    "palm_frond":     dict(base="#5a7630", roughness=0.62, bump=0.10, bump_scale=10, var_noise=8, grime=0.1),
    "palm_dead":      dict(base="#7d6a3a", roughness=0.90, bump=0.20, bump_scale=10, var_noise=8, grime=0.1),
    "la_mountain":    dict(base="#85796a", roughness=1.00, bump=0.50, bump_scale=3, var_noise=10, grime=0.0),
    "la_ground":      dict(base="#8c7f66", roughness=1.00, bump=0.30, bump_scale=6, var_noise=9, grime=0.0),
    "concrete_panel": dict(base="#8d8a84", roughness=0.84, bump=0.25, bump_scale=10, var_noise=4, grime=0.55),
    # glass / metal
    "glass":          dict(base="#22303a", roughness=0.06, metallic=0.15, bump=0.04, bump_scale=5, var_noise=1.5, grime=0.30, grime_tint=0.5, transmission=0.80, alpha=0.55, ior=1.45),
    "glass_dark":     dict(base="#141d24", roughness=0.10, metallic=0.25, bump=0.04, bump_scale=5, var_noise=1.5, grime=0.35, grime_tint=0.5, transmission=0.55, alpha=0.70),
    "glass_dirty":    dict(base="#3a3b36", roughness=0.35, metallic=0.10, bump=0.15, bump_scale=14, var_noise=6, grime=0.6, alpha=0.85),
    "metal":          dict(base="#71757a", roughness=0.42, metallic=0.90, bump=0.18, bump_scale=14, var_noise=4, grime=0.40),
    "metal_dark":     dict(base="#3a3c3f", roughness=0.50, metallic=0.85, bump=0.22, bump_scale=14, var_noise=4, grime=0.35),
    "metal_galv":     dict(base="#909699", roughness=0.55, metallic=0.80, bump=0.25, bump_scale=18, var_noise=6, grime=0.45),
    "rust":           dict(base="#8a4a2a", roughness=0.80, metallic=0.55, bump=0.55, bump_scale=24, var_noise=9, grime=0.6),
    "copper_patina":  dict(base="#4f7f6f", roughness=0.70, metallic=0.60, bump=0.35, bump_scale=18, var_noise=7, grime=0.5),
    "wood":           dict(base="#6b4a2f", roughness=0.86, bump=0.45, bump_scale=20, var_noise=8, grime=0.45),
    "wood_pale":      dict(base="#a08462", roughness=0.86, bump=0.45, bump_scale=20, var_noise=8, grime=0.4),
    "rubber":         dict(base="#1b1b1d", roughness=0.95, bump=0.30, bump_scale=22, var_noise=8, grime=0.25),
    # nature
    "grass":          dict(base="#4c5c34", roughness=0.95, bump=0.40, bump_scale=9, var_noise=8, grime=0.35),
    "grass_dry":      dict(base="#6d6a3d", roughness=0.95, bump=0.40, bump_scale=9, var_noise=8, grime=0.3),
    "dirt":           dict(base="#5a4a38", roughness=0.96, bump=0.45, bump_scale=7, var_noise=7, grime=0.3),
    "gravel":         dict(base="#6e6a63", roughness=0.95, bump=0.55, bump_scale=18, var_noise=9, grime=0.4),
    "foliage":        dict(base="#3d5929", roughness=0.90, bump=0.35, bump_scale=8, var_noise=9, grime=0.3),
    "foliage_dark":   dict(base="#2c421d", roughness=0.90, bump=0.35, bump_scale=8, var_noise=9, grime=0.3),
    "bark":           dict(base="#4a3a2c", roughness=0.92, bump=0.55, bump_scale=16, var_noise=10, grime=0.35),
    "water":          dict(base="#1b2a33", roughness=0.04, metallic=0.30, bump=0.06, bump_scale=3, var_noise=2, grime=0.2, transmission=0.55, alpha=0.85),
    # props / vehicles
    "car_paint_red":  dict(base="#8f2b28", roughness=0.30, metallic=0.35, bump=0.05, var_noise=3, grime=0.35),
    "car_paint_blue": dict(base="#2c4a70", roughness=0.30, metallic=0.35, bump=0.05, var_noise=3, grime=0.35),
    "car_paint_white": dict(base="#c9c8c2", roughness=0.32, metallic=0.30, bump=0.05, var_noise=3, grime=0.40),
    "car_paint_black": dict(base="#232427", roughness=0.28, metallic=0.40, bump=0.05, var_noise=3, grime=0.35),
    "car_paint_silver": dict(base="#9ea2a5", roughness=0.30, metallic=0.55, bump=0.05, var_noise=3, grime=0.35),
    "car_paint_taxi": dict(base="#c9a227", roughness=0.34, metallic=0.30, bump=0.05, var_noise=3, grime=0.4),
    "plastic":        dict(base="#2c2f33", roughness=0.60, bump=0.12, var_noise=5, grime=0.3),
    "cardboard":      dict(base="#8a6a45", roughness=0.95, bump=0.25, var_noise=9, grime=0.3),
    "paper":          dict(base="#cfc9bb", roughness=0.95, bump=0.15, var_noise=11, grime=0.25),
    "fabric_red":     dict(base="#7a3230", roughness=0.95, bump=0.20, var_noise=10, grime=0.3),
    "fabric_green":   dict(base="#33523c", roughness=0.95, bump=0.20, var_noise=10, grime=0.3),
}

PALETTE["interior_dark"] = dict(base="#14161a", roughness=0.88, bump=0.05,
                                grime=0.30, var_noise=2.0)

EMISSIVE = {
    "neon_pink":   ("#ff3d7f", 9.0),
    "neon_blue":   ("#3dd8ff", 8.0),
    "neon_red":    ("#ff3a2f", 9.0),
    "neon_green":  ("#54ff6a", 8.0),
    "lamp_warm":   ("#ffd7a0", 7.0),
    "lamp_cool":   ("#d8ecff", 6.0),
    "window_warm": ("#ffcf8a", 2.6),
    "window_cool": ("#bcd8f0", 2.2),
    "traffic_red": ("#ff2a1a", 9.0),
    "traffic_amber": ("#ffb020", 9.0),
    "traffic_green": ("#22ff66", 9.0),
    "screen_white": ("#dfefff", 3.0),
    "lamp_red":    ("#ff2a18", 4.0),
}


def make_pbr(name, base="#888888", roughness=0.6, metallic=0.0, bump=0.30,
             bump_scale=12.0, var_noise=4.0, grime=0.45, grime_tint=0.4,
             rough_var=0.18, transmission=0.0, alpha=1.0, ior=1.45):
    if name in MATS:
        return MATS[name]
    bc = hexc(base)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (760, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (440, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])

    tex = nt.nodes.new("ShaderNodeTexCoord"); tex.location = (-1120, 0)
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-940, 0)
    nt.links.new(tex.outputs["Object"], mp.inputs["Vector"])

    # --- base colour: noise -> 4 stop ramp (grime, dark, base, light)
    n_col = nt.nodes.new("ShaderNodeTexNoise"); n_col.location = (-720, 240)
    n_col.inputs["Scale"].default_value = var_noise
    n_col.inputs["Detail"].default_value = 8.0
    n_col.inputs["Roughness"].default_value = 0.62
    nt.links.new(mp.outputs["Vector"], n_col.inputs["Vector"])

    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-470, 240)
    stops = [(0.00, shade(bc, grime_tint)),
             (0.38, shade(bc, 0.76)),
             (0.64, bc),
             (0.93, shade(bc, 1.20))]
    els = ramp.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    while len(els) > len(stops):
        els.remove(els[-1])
    for idx, (pos, color) in enumerate(stops):
        els[idx].position = pos
        els[idx].color = color
    nt.links.new(n_col.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    # --- roughness variation
    n_r = nt.nodes.new("ShaderNodeTexNoise"); n_r.location = (-720, -60)
    n_r.inputs["Scale"].default_value = var_noise * 3.0
    n_r.inputs["Detail"].default_value = 6.0
    nt.links.new(mp.outputs["Vector"], n_r.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeValToRGB"); rr.location = (-470, -60)
    r0 = max(0.0, roughness - rough_var)
    r1 = min(1.0, roughness + rough_var)
    rr.color_ramp.elements[0].position = 0.0
    rr.color_ramp.elements[0].color = (r0, r0, r0, 1.0)
    rr.color_ramp.elements[1].position = 1.0
    rr.color_ramp.elements[1].color = (r1, r1, r1, 1.0)
    nt.links.new(n_r.outputs["Fac"], rr.inputs["Fac"])
    nt.links.new(rr.outputs["Color"], bsdf.inputs["Roughness"])

    # --- bump
    n_b = nt.nodes.new("ShaderNodeTexNoise"); n_b.location = (-720, -380)
    n_b.inputs["Scale"].default_value = bump_scale
    n_b.inputs["Detail"].default_value = 9.0
    n_b.inputs["Roughness"].default_value = 0.72
    nt.links.new(mp.outputs["Vector"], n_b.inputs["Vector"])
    bn = nt.nodes.new("ShaderNodeBump"); bn.location = (-210, -380)
    bn.inputs["Strength"].default_value = bump
    bn.inputs["Distance"].default_value = 0.08
    nt.links.new(n_b.outputs["Fac"], bn.inputs["Height"])
    nt.links.new(bn.outputs["Normal"], bsdf.inputs["Normal"])

    _setin(bsdf, "Metallic", metallic)
    _setin(bsdf, "IOR", ior)
    _setin(bsdf, "Alpha", alpha)
    _setin(bsdf, "Transmission Weight", transmission)
    if "Transmission Weight" not in bsdf.inputs:
        _setin(bsdf, "Transmission", transmission)

    mat.diffuse_color = bc
    try:
        mat.use_backface_culling = False
        if alpha < 1.0:
            mat.blend_method = "BLEND"
    except Exception:
        pass
    MATS[name] = mat
    return mat


def make_emissive(name, color, strength=6.0):
    if name in MATS:
        return MATS[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hexc(color)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    MATS[name] = mat
    return mat


def M(name):
    """Look up / lazily build a material by name.

    Accepts an already-resolved Material (callers sometimes pass one through),
    in which case it is returned unchanged.
    """
    if isinstance(name, bpy.types.Material):
        return name
    if name is None:
        return None
    if name in MATS:
        return MATS[name]
    if name in EMISSIVE:
        color, strength = EMISSIVE[name]
        return make_emissive(name, color, strength)
    spec = PALETTE.get(name)
    if spec is None:
        spec = dict(base="#8a8a8a", roughness=0.6)
    return make_pbr(name, **spec)


def save_blend(path=None):
    """Write the built city to a .blend, packing external images so the file
    is self-contained and openable anywhere."""
    import bpy as _bpy
    path = path or os.path.join(CONFIG["out_dir"], CONFIG["blend_name"])
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        _bpy.ops.file.pack_all()
    except Exception as exc:
        print("  (could not pack images: {})".format(exc))
    _bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    size = os.path.getsize(path) / (1024.0 * 1024.0)
    print("  saved {}  ({:.1f} MB)".format(path, size))
    return path


def build_all_materials():
    for name in PALETTE:
        M(name)
    for name in EMISSIVE:
        M(name)
    return len(MATS)


# -----------------------------------------------------------------------------
# Geometry helpers
# -----------------------------------------------------------------------------
def _finish(obj, mat, collection, bevel=0.0, smooth=False):
    link_object(obj, collection if collection is not None else col("CITY_Misc"))
    if mat is not None:
        obj.data.materials.append(mat if isinstance(mat, bpy.types.Material) else M(mat))
    if bevel and bevel > 0.0:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(30.0)
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def new_mesh_obj(name, mesh, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler = rot
    obj.scale = scale
    return obj


def add_box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, collection=None,
            bevel=0.0, smooth=False):
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()
    obj = new_mesh_obj(name, mesh, loc, rot)
    return _finish(obj, mat, collection, bevel, smooth)


def _cylinder_mesh(name, radius, depth, segments=16, radius_top=None):
    rt = radius if radius_top is None else radius_top
    bm = bmesh.new()
    bot = []
    top = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        bot.append(bm.verts.new((radius * math.cos(a), radius * math.sin(a), -depth * 0.5)))
        top.append(bm.verts.new((rt * math.cos(a), rt * math.sin(a), depth * 0.5)))
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    if radius > 1e-6:
        bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def add_cylinder(name, radius, depth, loc=(0, 0, 0), rot=(0, 0, 0), mat=None,
                 collection=None, segments=16, radius_top=None, smooth=True,
                 bevel=0.0):
    mesh = _cylinder_mesh(name, radius, depth, segments, radius_top)
    obj = new_mesh_obj(name, mesh, loc, rot)
    return _finish(obj, mat, collection, bevel, smooth)


def add_plane(name, size, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, collection=None,
              subdiv=1, smooth=False):
    sx, sy = size
    nx = max(1, int(subdiv))
    ny = max(1, int(subdiv))
    bm = bmesh.new()
    grid = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            x = -sx * 0.5 + sx * i / nx
            y = -sy * 0.5 + sy * j / ny
            grid[(i, j)] = bm.verts.new((x, y, 0.0))
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((grid[(i, j)], grid[(i + 1, j)],
                          grid[(i + 1, j + 1)], grid[(i, j + 1)]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = new_mesh_obj(name, mesh, loc, rot)
    return _finish(obj, mat, collection, 0.0, smooth)


def add_grid_surface(name, x0, x1, y0, y1, nx, ny, zfunc, mat=None, collection=None,
                     smooth=True):
    bm = bmesh.new()
    grid = {}
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        for j in range(ny + 1):
            y = y0 + (y1 - y0) * j / ny
            grid[(i, j)] = bm.verts.new((x, y, zfunc(x, y)))
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((grid[(i, j)], grid[(i + 1, j)],
                          grid[(i + 1, j + 1)], grid[(i, j + 1)]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = new_mesh_obj(name, mesh)
    return _finish(obj, mat, collection, 0.0, smooth)


def add_rock(name, size, loc, rot=(0, 0, 0), mat="stone_dark", collection=None, seed=0):
    R = random.Random(seed)
    bm = bmesh.new()
    try:
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    except TypeError:
        bmesh.ops.create_icosphere(bm, subdivisions=2, diameter=1.0)
    for v in bm.verts:
        f = 1.0 + (R.random() - 0.5) * 0.45
        v.co.x *= size[0] * 0.5 * f
        v.co.y *= size[1] * 0.5 * f
        v.co.z *= size[2] * 0.5 * f
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = new_mesh_obj(name, mesh, loc, rot)
    return _finish(obj, mat, collection, 0.0, False)


def add_polyline_strip(name, points, width, loc=(0, 0, 0), mat=None, collection=None,
                       z=0.0):
    """Flat ribbon following a 2D polyline (used for cracks, paint lines)."""
    bm = bmesh.new()
    rows = []
    for k, (px, py) in enumerate(points):
        if k == 0:
            dx = points[1][0] - px
            dy = points[1][1] - py
        elif k == len(points) - 1:
            dx = px - points[k - 1][0]
            dy = py - points[k - 1][1]
        else:
            dx = points[k + 1][0] - points[k - 1][0]
            dy = points[k + 1][1] - points[k - 1][1]
        ln = math.hypot(dx, dy) or 1.0
        nxv = -dy / ln * width * 0.5
        nyv = dx / ln * width * 0.5
        a = bm.verts.new((px + nxv, py + nyv, z))
        b = bm.verts.new((px - nxv, py - nyv, z))
        rows.append((a, b))
    for k in range(len(rows) - 1):
        bm.faces.new((rows[k][1], rows[k][0], rows[k + 1][0], rows[k + 1][1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = new_mesh_obj(name, mesh, loc)
    return _finish(obj, mat, collection, 0.0, False)


def jitter_verts(obj, amount=0.02, seed=0):
    R = random.Random(seed)
    for v in obj.data.vertices:
        v.co.x += (R.random() - 0.5) * amount
        v.co.y += (R.random() - 0.5) * amount
        v.co.z += (R.random() - 0.5) * amount
    return obj


def shade_smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


# -----------------------------------------------------------------------------
# Duplication / instancing
# -----------------------------------------------------------------------------
def linked_duplicate(obj, name=None, collection=None, loc=None, rot=None):
    dup = obj.copy()              # shares mesh + material data
    dup.name = name or (obj.name + "_lnk")
    if loc is not None:
        dup.location = loc
    if rot is not None:
        dup.rotation_euler = rot
    link_object(dup, collection if collection is not None else col("CITY_Misc"))
    return dup


def instance_collection(src_collection, name, loc=(0, 0, 0), rot=(0, 0, 0),
                        collection=None):
    empty = bpy.data.objects.new(name, None)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = src_collection
    empty.location = loc
    empty.rotation_euler = rot
    link_object(empty, collection if collection is not None else col("CITY_Misc"))
    return empty


def scatter_on_rect(name, base_obj, rect, count, R, collection=None, z=0.0,
                    min_dist=2.0, jitter_scale=(1, 1), avoid=None):
    """Linked-duplicate scatter inside a rectangle. Returns placed objects."""
    placed = []
    x0, y0, x1, y1 = rect
    tries = 0
    while len(placed) < count and tries < count * 30:
        tries += 1
        x = R.uniform(x0, x1)
        y = R.uniform(y0, y1)
        if avoid is not None and avoid(x, y):
            continue
        if any((x - p[0]) ** 2 + (y - p[1]) ** 2 < min_dist ** 2 for p in placed):
            continue
        placed.append((x, y))
        o = linked_duplicate(base_obj, name="{}_{:03d}".format(name, len(placed)),
                             collection=collection, loc=(x, y, z),
                             rot=(0, 0, R.uniform(0, math.tau)))
        s = R.uniform(jitter_scale[0], jitter_scale[1])
        o.scale = (o.scale[0] * s, o.scale[1] * s, o.scale[2] * s)
    return placed


# -----------------------------------------------------------------------------
# MASTERPLAN
# -----------------------------------------------------------------------------
def _partition(total, R, target, widths):
    pos = -total * 0.5
    blocks = []
    roads = []
    while pos < total * 0.5 - 1e-6:
        w = target * R.uniform(0.70, 1.40)
        if pos + w > total * 0.5:
            w = total * 0.5 - pos
        blocks.append((pos, pos + w))
        pos += w
        if pos < total * 0.5 - 1e-6:
            rw = R.choice(widths) * R.uniform(0.9, 1.1)
            rw = min(rw, total * 0.5 - pos - 0.01)
            if rw < 6.0:
                break
            roads.append((pos + rw * 0.5, rw))
            pos += rw
    return blocks, roads


def _classify(cx, cy, half):
    nx = cx / half
    ny = cy / half
    if ny < -0.58:
        return "waterfront"
    if nx > 0.48 and ny > 0.05:
        return "industrial"
    r = max(abs(nx), abs(ny))
    if is_la():
        # polycentric sprawl: a small downtown cluster, low-rise everywhere else
        if r < 0.17:
            return "downtown"
        if r < 0.45:
            return "midtown"
        return "residential"
    if r < 0.30:
        return "downtown"
    if r < 0.62:
        return "midtown"
    return "residential"


def _road_kind(dist_norm):
    if dist_norm < 0.35:
        return "arterial"
    if dist_norm < 0.70:
        return "collector"
    return "residential"


def plan_city(force=False):
    global CITY_PLAN
    if CITY_PLAN and not force:
        return CITY_PLAN
    R = rng("plan")
    size = CONFIG["city_size"]
    half = size * 0.5

    if is_la():
        # LA: big blocks, wide boulevards (5-9 lanes), nothing like Manhattan
        target, widths = 92.0, [16, 20, 24, 28]
    else:
        target, widths = 66.0, [10, 12, 14, 16]
    bx, rx = _partition(size, R, target, widths)
    by, ry = _partition(size, R, target, widths)

    roads_x = [{"c": c, "w": w, "kind": _road_kind(abs(c) / half), "axis": "x"}
               for (c, w) in rx]
    roads_y = [{"c": c, "w": w, "kind": _road_kind(abs(c) / half), "axis": "y"}
               for (c, w) in ry]

    blocks = []
    for (x0, x1) in bx:
        for (y0, y1) in by:
            cx = (x0 + x1) * 0.5
            cy = (y0 + y1) * 0.5
            blocks.append({
                "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                "cx": cx, "cy": cy,
                "w": x1 - x0, "h": y1 - y0,
                "district": _classify(cx, cy, half),
            })

    # carve parkland out of two residential blocks
    parks = []
    candidates = [b for b in blocks if b["district"] == "residential"]
    candidates.sort(key=lambda b: (b["cx"] ** 2 + (b["cy"] - half * 0.3) ** 2))
    for b in candidates[:2]:
        b["district"] = "parkland"
        parks.append(b)

    intersections = []
    for rx_ in roads_x:
        for ry_ in roads_y:
            intersections.append({
                "x": rx_["c"], "y": ry_["c"],
                "w": rx_["w"], "h": ry_["w"],
                "kind": rx_["kind"] if rx_["w"] > ry_["w"] else ry_["kind"],
            })

    plan = {
        "seed": CONFIG["seed"],
        "size": size,
        "half": half,
        "roads_x": roads_x,
        "roads_y": roads_y,
        "blocks": blocks,
        "intersections": intersections,
        "parks": parks,
        "water_y": -half,
        "highway_y": half + 30.0,
    }
    CITY_PLAN = plan
    try:
        with open(os.path.join(CONFIG["out_dir"], "city_plan.json"), "w") as fh:
            json.dump(plan, fh, indent=1)
    except Exception:
        pass
    return plan


# -----------------------------------------------------------------------------
# Report
# -----------------------------------------------------------------------------
def collection_stats():
    stats = {}
    for c in bpy.data.collections:
        nobj = 0
        tris = 0
        for o in c.objects:
            if o.type == "MESH" and o.data is not None:
                nobj += 1
                me = o.data
                tris += sum(max(0, len(p.vertices) - 2) for p in me.polygons)
        if nobj or c.children:
            stats[c.name] = (nobj, tris)
    return stats


def report(verbose=True):
    stats = collection_stats()
    total_obj = sum(v[0] for v in stats.values())
    total_tri = sum(v[1] for v in stats.values())
    if verbose:
        print("\n" + "-" * 78)
        print(" {:<38} {:>10} {:>14}".format("COLLECTION", "OBJECTS", "TRIANGLES"))
        print("-" * 78)
        for name in sorted(stats):
            nobj, tris = stats[name]
            if nobj == 0:
                continue
            print(" {:<38} {:>10} {:>14,}".format(name[:38], nobj, tris))
        print("-" * 78)
        print(" {:<38} {:>10} {:>14,}".format("TOTAL", total_obj, total_tri))
        print("-" * 78 + "\n")
    data = {"objects": total_obj, "triangles": total_tri,
            "collections": {k: {"objects": v[0], "triangles": v[1]}
                            for k, v in stats.items()},
            "config": dict(CONFIG)}
    try:
        with open(os.path.join(CONFIG["out_dir"], "city_report.json"), "w") as fh:
            json.dump(data, fh, indent=1)
    except Exception:
        pass
    return data


# -----------------------------------------------------------------------------
# Standalone entry
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    bootstrap(banner="M0 CORE FRAMEWORK")
    n_mats = build_all_materials()
    plan = plan_city()
    print("  materials built : {}".format(n_mats))
    print("  blocks          : {}".format(len(plan["blocks"])))
    print("  road lines      : {} x  /  {} y".format(
        len(plan["roads_x"]), len(plan["roads_y"])))
    print("  intersections   : {}".format(len(plan["intersections"])))
    print("  districts       : {}".format(
        ", ".join(sorted({b["district"] for b in plan["blocks"]}))))
    report()
