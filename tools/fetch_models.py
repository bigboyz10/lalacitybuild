#!/usr/bin/env python3
"""Download CC0 photoscanned models from Poly Haven for the city build.

Usage:  python3 tools/fetch_models.py [--res 1k] [--only key1,key2] [--list]

Only models that are cheap enough to instance thousands of times are listed
here; Poly Haven's hero trees run to ~500 MB of geometry each, which a city
cannot afford, so foliage at that scale stays procedural.

Everything downloaded is CC0. Files land in assets/models/<key>/.
"""
import argparse
import json
import os
import sys
import urllib.request

API = "https://api.polyhaven.com"
UA = {"User-Agent": "lalacitybuild/1.0 (Blender city generator)"}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(HERE, "assets", "models")

# key -> Poly Haven slug.  Sizes are the 1k gltf payload, measured.
MODELS = {
    # street furniture
    "hydrant":        "fire_hydrant",             # 5.5 MB
    "trash_can":      "metal_trash_can",          # 5.0 MB
    "bench":          "painted_wooden_bench",     # 2.0 MB
    "road_barrier":   "concrete_road_barrier",    # 3.8 MB
    "road_barrier_2": "concrete_road_barrier_02",
    "barrel":         "Barrel_01",                # 0.7 MB
    "barrel_rust":    "barrel_03",
    "cardboard_box":  "cardboard_box_01",         # 2.2 MB
    "trashbag":       "trashbag",
    "aircon":         "exterior_aircon_unit",     # 7.7 MB
    "planter":        "planter_box_01",           # 2.3 MB
    "wet_sign":       "WetFloorSign_01",
    # vegetation small enough to scatter
    "grass_tuft":     "grass_medium_01",          # 3.1 MB
    "grass_tuft_2":   "grass_medium_02",
    "grass_bermuda":  "grass_bermuda_01",
    "weed_dandelion": "dandelion_01",             # 3.1 MB
    "weed_nettle":    "nettle_plant",             # 2.5 MB
    "fern":           "fern_02",                  # 1.1 MB
    "bush":           "wild_rooibos_bush",        # 2.5 MB
    "potted_plant":   "potted_plant_01",          # 6.3 MB
    # rock / debris
    "boulder":        "boulder_01",               # 5.8 MB
    "dead_trunk":     "dead_tree_trunk",          # 4.8 MB
}


def _get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def _download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 256:
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as src, open(tmp, "wb") as out:
        n = 0
        while True:
            chunk = src.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            n += len(chunk)
    os.replace(tmp, dest)
    return n


def fetch_model(key, slug, res):
    try:
        files = _get_json("{}/files/{}".format(API, slug))
        entry = files["gltf"][res]["gltf"]
    except Exception as exc:
        print("  !! {:16s} {:26s} {}".format(key, slug, exc))
        return 0
    folder = os.path.join(MODEL_DIR, key)
    total = 0
    try:
        total += _download(entry["url"], os.path.join(folder, slug + "_" + res + ".gltf"))
        for rel, info in entry.get("include", {}).items():
            total += _download(info["url"], os.path.join(folder, rel.replace("/", os.sep)))
    except Exception as exc:
        print("  !! {:16s} {}".format(key, exc))
        return 0
    print("  {:16s} {:26s} {:>7}".format(
        key, slug, "cached" if total == 0 else "{:.1f} MB".format(total / 1e6)))
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="1k")
    ap.add_argument("--only", default="")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        for k, v in MODELS.items():
            print("  {:16s} {}".format(k, v))
        return 0
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    print("Poly Haven CC0 models -> {}".format(MODEL_DIR))
    total = 0
    for key, slug in MODELS.items():
        if only and key not in only:
            continue
        total += fetch_model(key, slug, args.res)
    print("downloaded {:.1f} MB".format(total / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
