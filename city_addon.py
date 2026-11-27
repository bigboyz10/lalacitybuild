# =============================================================================
#  CITY BUILD  --  BLENDER ADD-ON
#  Puts the whole generator in Blender's UI so the city can be built, tweaked
#  and re-rolled from the N-panel without touching a terminal.
#
#  Install:  Edit > Preferences > Add-ons > Install... > pick this file > tick it
#  Use:      3D Viewport > press N > "City" tab
# =============================================================================
bl_info = {
    "name": "City Build",
    "author": "lalacitybuild",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > City",
    "description": "Procedural realistic city generator with photographic PBR assets",
    "category": "Add Mesh",
}

import importlib
import os
import sys

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup

# the generator modules live next to this file
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

def _load_pipeline():
    """Read the module list straight out of master.py so the panel never drifts
    out of sync when the pipeline gains or loses a stage."""
    try:
        import master
        importlib.reload(master)
        return [(key, mod) for (key, mod, _fn) in master.PIPELINE]
    except Exception:
        return [("terrain", "terrain"), ("roads", "roads"),
                ("sidewalks", "sidewalks"), ("buildings", "buildings_types")]


PIPELINE_KEYS = _load_pipeline()


# -----------------------------------------------------------------------------
class CityProps(PropertyGroup):
    seed: IntProperty(name="Seed", default=1337, min=0, max=999999,
                      description="Change this to roll an entirely different city")
    size: FloatProperty(name="Size (m)", default=480.0, min=80.0, max=2000.0,
                        description="City footprint in metres. 900 m is ~25k objects")
    density: FloatProperty(name="Density", default=0.85, min=0.05, max=1.0,
                           description="Fraction of lots that receive buildings")
    quality: EnumProperty(
        name="Quality",
        items=[("preview", "Preview", "Faster build, lighter detail"),
               ("high", "High", "Cycles, displacement, full detail")],
        default="preview")
    use_textures: BoolProperty(
        name="Photographic PBR", default=True,
        description="Use the downloaded CC0 texture sets and HDRI sky")
    build_people: BoolProperty(name="People", default=True)
    build_models: BoolProperty(name="Scanned props", default=True)
    build_vehicles: BoolProperty(name="Vehicles", default=True)
    build_vegetation: BoolProperty(name="Vegetation", default=True)
    build_trees: BoolProperty(name="Trees", default=True)
    build_traffic: BoolProperty(name="Traffic", default=True)
    build_signage: BoolProperty(name="Signage", default=True)
    build_animals: BoolProperty(name="Animals", default=True)
    out_dir: StringProperty(name="Output", subtype="DIR_PATH",
                            default="//", description="Where renders and exports go")


def _reload_core():
    import core
    importlib.reload(core)
    return core


def _apply_props(C, props, only=None):
    C.CONFIG["seed"] = props.seed
    C.CONFIG["city_size"] = props.size
    C.CONFIG["density"] = props.density
    C.CONFIG["quality"] = props.quality
    C.CONFIG["textures"] = props.use_textures
    C.CONFIG["render"] = False
    C.CONFIG["save_blend"] = False
    C.CONFIG["only"] = only or []
    out = bpy.path.abspath(props.out_dir) if props.out_dir else _HERE
    C.CONFIG["out_dir"] = out
    try:
        os.makedirs(out, exist_ok=True)
    except Exception:
        C.CONFIG["out_dir"] = _HERE


def _enabled_keys(props):
    skip = set()
    if not props.build_people:
        skip.add("people")
    if not props.build_models:
        skip.add("models")
    if not props.build_vehicles:
        skip.add("vehicles")
    if not props.build_vegetation:
        skip.add("vegetation")
    if not props.build_trees:
        skip.add("trees")
    if not props.build_traffic:
        skip.add("traffic")
    if not props.build_signage:
        skip.add("signage")
    if not props.build_animals:
        skip.add("animals")
    return [(k, m) for (k, m) in _load_pipeline() if k not in skip]


# -----------------------------------------------------------------------------
class CITY_OT_build(Operator):
    bl_idname = "city.build"
    bl_label = "Build City"
    bl_description = "Wipe the scene and generate a complete city"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.city_props
        try:
            C = _reload_core()
        except Exception as exc:
            self.report({"ERROR"}, "core.py not importable: {}".format(exc))
            return {"CANCELLED"}

        _apply_props(C, props)
        C.bootstrap(banner="CITY BUILD  (add-on)")
        C.build_all_materials()

        if props.use_textures:
            try:
                import assets_pbr
                importlib.reload(assets_pbr)
                assets_pbr.build()
            except Exception as exc:
                print("texture pass failed:", exc)

        built, failed = 0, []
        for key, mod_name in _enabled_keys(props):
            try:
                mod = importlib.import_module(mod_name)
                importlib.reload(mod)
                mod.build()
                built += 1
            except Exception as exc:
                failed.append("{} ({})".format(key, exc))
                print("  !! {} failed: {}".format(key, exc))

        try:
            import render_export
            importlib.reload(render_export)
            render_export.build_cameras()
        except Exception as exc:
            print("cameras failed:", exc)

        data = C.report()
        msg = "Built {} modules - {} objects, {:,} triangles".format(
            built, data["objects"], data["triangles"])
        if failed:
            msg += "  |  failed: " + ", ".join(failed)
            self.report({"WARNING"}, msg)
        else:
            self.report({"INFO"}, msg)
        return {"FINISHED"}


class CITY_OT_rebuild_part(Operator):
    bl_idname = "city.rebuild_part"
    bl_label = "Rebuild Module"
    bl_description = "Re-run a single module without rebuilding the whole city"
    bl_options = {"REGISTER", "UNDO"}

    module: StringProperty(default="people")

    def execute(self, context):
        props = context.scene.city_props
        C = _reload_core()
        _apply_props(C, props, only=[self.module])
        name = dict(_load_pipeline()).get(self.module, self.module)
        try:
            mod = importlib.import_module(name)
            importlib.reload(mod)
            mod.build()
        except Exception as exc:
            self.report({"ERROR"}, "{} failed: {}".format(self.module, exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Rebuilt {}".format(self.module))
        return {"FINISHED"}


class CITY_OT_reroll(Operator):
    bl_idname = "city.reroll"
    bl_label = "Re-roll Seed"
    bl_description = "Pick a new random seed and rebuild"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        import random
        context.scene.city_props.seed = random.randint(0, 999999)
        return bpy.ops.city.build()


class CITY_OT_save_blend(Operator):
    bl_idname = "city.save_blend"
    bl_label = "Save .blend"
    bl_description = "Pack all textures and save a standalone .blend"

    filepath: StringProperty(subtype="FILE_PATH", default="//city.blend")

    def execute(self, context):
        try:
            bpy.ops.file.pack_all()
        except Exception as exc:
            print("pack failed:", exc)
        path = bpy.path.abspath(self.filepath)
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        self.report({"INFO"}, "Saved {}".format(path))
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class CITY_OT_fetch_assets(Operator):
    bl_idname = "city.fetch_assets"
    bl_label = "Download CC0 Assets"
    bl_description = "Fetch the Poly Haven texture sets and models (needs internet)"

    def execute(self, context):
        import subprocess
        ok = []
        for script in ("tools/fetch_assets.py", "tools/fetch_models.py"):
            path = os.path.join(_HERE, script)
            if not os.path.exists(path):
                continue
            try:
                subprocess.run([sys.executable, path, "--res", "1k"],
                               cwd=_HERE, timeout=1800, check=False)
                ok.append(script)
            except Exception as exc:
                self.report({"WARNING"}, "{}: {}".format(script, exc))
        self.report({"INFO"}, "Fetched: {}".format(", ".join(ok) or "nothing"))
        return {"FINISHED"}


# -----------------------------------------------------------------------------
class CITY_PT_main(Panel):
    bl_label = "City Build"
    bl_idname = "CITY_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "City"

    def draw(self, context):
        layout = self.layout
        props = context.scene.city_props

        col = layout.column(align=True)
        col.prop(props, "seed")
        col.prop(props, "size")
        col.prop(props, "density")
        col.prop(props, "quality")

        layout.separator()
        box = layout.box()
        box.label(text="Include")
        grid = box.grid_flow(columns=2, even_columns=True)
        grid.prop(props, "build_people")
        grid.prop(props, "build_models")
        grid.prop(props, "build_vehicles")
        grid.prop(props, "build_vegetation")
        grid.prop(props, "build_trees")
        grid.prop(props, "build_traffic")
        grid.prop(props, "build_signage")
        grid.prop(props, "build_animals")
        box.prop(props, "use_textures")

        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 1.6
        row.operator("city.build", icon="MOD_BUILD")
        layout.operator("city.reroll", icon="FILE_REFRESH")

        layout.separator()
        layout.label(text="Rebuild one module")
        flow = layout.grid_flow(columns=2, even_columns=True, align=True)
        for key, _mod in _load_pipeline():
            op = flow.operator("city.rebuild_part", text=key.capitalize())
            op.module = key

        layout.separator()
        layout.operator("city.save_blend", icon="FILE_BLEND")
        layout.operator("city.fetch_assets", icon="IMPORT")


CLASSES = (CityProps, CITY_OT_build, CITY_OT_rebuild_part, CITY_OT_reroll,
           CITY_OT_save_blend, CITY_OT_fetch_assets, CITY_PT_main)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.city_props = bpy.props.PointerProperty(type=CityProps)


def unregister():
    del bpy.types.Scene.city_props
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
