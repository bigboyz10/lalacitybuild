"""Single source of truth for the downloadable asset library.

Every entry is CC0 from Poly Haven.  `height` normalises the scan to a real
world size in metres; `tris` is the triangle budget the baker decimates to
before the compact .glb is written into assets/lib/ and committed.

Raw downloads (assets/raw/) are large and gitignored.  Baked .glb files are
small and tracked, so a fresh clone has the whole library without re-downloading
hundreds of megabytes.
"""

MODELS = {
    # ---- trees & large vegetation (huge scans, decimated hard) -----------
    "tree_island_01":   dict(slug="island_tree_01",        height=8.5,  tris=6000,  tags=["tree"]),
    "tree_island_02":   dict(slug="island_tree_02",        height=7.2,  tris=6000,  tags=["tree"]),
    "tree_island_03":   dict(slug="island_tree_03",        height=9.0,  tris=6000,  tags=["tree"]),
    "tree_fir":         dict(slug="fir_tree_01",           height=11.0, tris=7000,  tags=["tree"]),
    "tree_fir_sapling": dict(slug="fir_sapling_medium",    height=3.2,  tris=3000,  tags=["tree", "sapling"]),
    "tree_dead":        dict(slug="dead_tree_trunk",       height=5.5,  tris=2500,  tags=["tree", "dead"]),
    "tree_dead_02":     dict(slug="dead_tree_trunk_02",    height=4.8,  tris=2500,  tags=["tree", "dead"]),
    "tree_stump":       dict(slug="tree_stump_01",         height=0.75, tris=1200,  tags=["debris"]),
    "tree_stump_02":    dict(slug="tree_stump_02",         height=0.60, tris=1200,  tags=["debris"]),

    # ---- shrubs, ferns, flowers, ground cover ---------------------------
    "shrub_01":         dict(slug="shrub_01",              height=1.10, tris=1800,  tags=["shrub"]),
    "shrub_02":         dict(slug="shrub_02",              height=0.95, tris=1800,  tags=["shrub"]),
    "shrub_03":         dict(slug="shrub_03",              height=0.80, tris=1500,  tags=["shrub"]),
    "shrub_04":         dict(slug="shrub_04",              height=1.25, tris=1800,  tags=["shrub"]),
    "bush_rooibos":     dict(slug="wild_rooibos_bush",     height=0.85, tris=1800,  tags=["shrub"]),
    "fern":             dict(slug="fern_02",               height=0.50, tris=1200,  tags=["ground"]),
    "grass_tuft":       dict(slug="grass_medium_01",       height=0.28, tris=900,   tags=["grass"]),
    "grass_tuft_2":     dict(slug="grass_medium_02",       height=0.32, tris=900,   tags=["grass"]),
    "grass_bermuda":    dict(slug="grass_bermuda_01",      height=0.18, tris=700,   tags=["grass"]),
    "weed_dandelion":   dict(slug="dandelion_01",          height=0.24, tris=700,   tags=["weed"]),
    "weed_nettle":      dict(slug="nettle_plant",          height=0.45, tris=900,   tags=["weed"]),
    "weed_celandine":   dict(slug="celandine_01",          height=0.22, tris=700,   tags=["weed"]),
    "flower_gazania":   dict(slug="flower_gazania",        height=0.25, tris=700,   tags=["flower"]),
    "flower_ursinia":   dict(slug="flower_ursinia",        height=0.28, tris=700,   tags=["flower"]),
    "flower_heliophila":dict(slug="flower_heliophila",     height=0.30, tris=700,   tags=["flower"]),
    "moss":             dict(slug="moss_01",               height=0.06, tris=500,   tags=["ground"]),
    "branches_dry":     dict(slug="dry_branches_medium_01",height=0.35, tris=900,   tags=["debris"]),
    "bark_debris":      dict(slug="bark_debris_01",        height=0.10, tris=500,   tags=["debris"]),

    # ---- rocks & landscape ----------------------------------------------
    "boulder_01":       dict(slug="boulder_01",            height=0.70, tris=900,   tags=["rock"]),
    "boulder_02":       dict(slug="namaqualand_boulder_02",height=1.10, tris=1200,  tags=["rock"]),
    "boulder_03":       dict(slug="namaqualand_boulder_03",height=0.85, tris=1200,  tags=["rock"]),
    "boulder_04":       dict(slug="namaqualand_boulder_04",height=1.40, tris=1500,  tags=["rock"]),
    "rocks_coast":      dict(slug="coast_rocks_01",        height=1.20, tris=2000,  tags=["rock"]),
    "rock_moss":        dict(slug="rock_moss_set_01",      height=0.45, tris=1200,  tags=["rock"]),

    # ---- street furniture -------------------------------------------------
    "hydrant":          dict(slug="fire_hydrant",          height=0.78, tris=2200,  tags=["street"]),
    "trash_can":        dict(slug="metal_trash_can",       height=0.95, tris=1800,  tags=["street"]),
    "bench":            dict(slug="painted_wooden_bench",  height=0.86, tris=2000,  tags=["street"]),
    "planter":          dict(slug="planter_box_01",        height=0.55, tris=1200,  tags=["street"]),
    "planter_02":       dict(slug="planter_box_02",        height=0.60, tris=1200,  tags=["street"]),
    "potted_plant":     dict(slug="potted_plant_01",       height=0.65, tris=1800,  tags=["street"]),
    "road_barrier":     dict(slug="concrete_road_barrier", height=0.82, tris=900,   tags=["street"]),
    "road_barrier_2":   dict(slug="concrete_road_barrier_02", height=0.82, tris=900, tags=["street"]),
    "chainlink_fence":  dict(slug="modular_chainlink_fence", height=2.00, tris=1500, tags=["street"]),
    "electricity_pole": dict(slug="modular_electricity_poles", height=8.00, tris=2000, tags=["street"]),
    "flood_light":      dict(slug="flood_lights",          height=1.60, tris=1800,  tags=["street"]),
    "wet_sign":         dict(slug="WetFloorSign_01",       height=0.62, tris=700,   tags=["street"]),
    "aircon":           dict(slug="exterior_aircon_unit",  height=0.70, tris=1500,  tags=["roof"]),

    # ---- industrial / alley clutter ---------------------------------------
    "barrel":           dict(slug="Barrel_01",             height=0.88, tris=900,   tags=["clutter"]),
    "barrel_02":        dict(slug="Barrel_02",             height=0.88, tris=900,   tags=["clutter"]),
    "barrel_rust":      dict(slug="barrel_03",             height=0.88, tris=900,   tags=["clutter"]),
    "crate_wood":       dict(slug="wooden_crate_01",       height=0.45, tris=700,   tags=["clutter"]),
    "crate_wood_02":    dict(slug="wooden_crate_02",       height=0.50, tris=700,   tags=["clutter"]),
    "crate_plastic":    dict(slug="plastic_crate_01",      height=0.32, tris=700,   tags=["clutter"]),
    "crate_plastic_02": dict(slug="plastic_crate_02",      height=0.32, tris=700,   tags=["clutter"]),
    "cardboard_box":    dict(slug="cardboard_box_01",      height=0.42, tris=500,   tags=["clutter"]),
    "trashbag":         dict(slug="trashbag",              height=0.62, tris=900,   tags=["clutter"]),
    "compost_bag":      dict(slug="compost_bag_02",        height=0.55, tris=700,   tags=["clutter"]),
    "cement_bag":       dict(slug="cement_bag",            height=0.28, tris=500,   tags=["clutter"]),
    "jerrycan":         dict(slug="metal_jerrycan",        height=0.45, tris=700,   tags=["clutter"]),
    "can_rusted":       dict(slug="can_rusted",            height=0.14, tris=400,   tags=["clutter"]),
    "bottle_gallon":    dict(slug="plastic_bottle_gallon", height=0.30, tris=500,   tags=["clutter"]),
    "wheel_rim":        dict(slug="rusted_wheel_rim_01",   height=0.55, tris=900,   tags=["clutter"]),
    "pipes":            dict(slug="modular_pipes",         height=1.20, tris=1500,  tags=["clutter"]),
    "hand_truck":       dict(slug="hand_truck",            height=1.20, tris=1200,  tags=["clutter"]),
    "storage_cart":     dict(slug="industrial_storage_cart", height=1.00, tris=1500, tags=["clutter"]),
    "coffee_cart":      dict(slug="CoffeeCart_01",         height=1.80, tris=2500,  tags=["street"]),
}

# material-name -> texture set, for assets_pbr.py
TEXTURES = {
    "asphalt":        "asphalt_02",
    "asphalt_worn":   "asphalt_04",
    "concrete":       "concrete_floor_worn_001",
    "concrete_wall":  "concrete_wall_008",
    "pavement":       "concrete_pavers_02",
    "brick_old":      "red_brick_03",
    "brick_modern":   "brick_wall_006",
    "plaster":        "beige_wall_001",
    "stone_old":      "cobblestone_floor_01",
    "metal_dark":     "metal_plate",
    "rust":           "rusty_metal_sheet",
    "roof_tar":       "grey_roof_tiles",
    "grass":          "aerial_grass_rock",
    "tiles_floor":    "floor_tiles_06",
}


def by_tag(tag):
    return [k for k, v in MODELS.items() if tag in v["tags"]]
