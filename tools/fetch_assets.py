#!/usr/bin/env python3
"""Download CC0 PBR textures + an HDRI sky from Poly Haven for the city build.

Usage:  python3 tools/fetch_assets.py [--res 2k] [--only key1,key2]

Everything Poly Haven serves is CC0, so the results are redistributable.
Files land in assets/textures/<key>/ and assets/hdri/.  Downloads are skipped
when the file already exists, so re-running is cheap and resumable.
"""
import argparse
import json
import os
import sys
import urllib.request

API = "https://api.polyhaven.com"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX_DIR = os.path.join(HERE, "assets", "textures")
HDRI_DIR = os.path.join(HERE, "assets", "hdri")

# city-material key -> Poly Haven texture slug
TEXTURES = {
    "asphalt":        "asphalt_02",
    "asphalt_worn":   "asphalt_04",
    "concrete":       "concrete_floor_worn_001",
    "concrete_wall":  "concrete_wall_008",
    "pavement":       "concrete_pavers_02",
    "brick_old":      "red_brick_03",
    "brick_modern":   "brick_wall_006",
    "plaster":        "beige_wall_001",
    "stone_old":      "stone_wall_015",
    "metal_dark":     "metal_plate",
    "rust":           "rusty_metal_sheet",
    "roof_tar":       "roofing_shingles",
    "grass":          "aerial_grass_rock",
    "tiles_floor":    "floor_tiles_06",
}

# which PBR maps we want, in Blender-friendly order
MAPS = ["Diffuse", "diff", "albedo", "Rough", "rough", "nor_gl", "Displacement", "disp", "AO", "ao", "arm"]
WANTED = {"diff": "diffuse", "rough": "roughness", "nor_gl": "normal", "ao": "ao", "disp": "displacement"}

HDRI = "kloppenheim_06_puresky"


def _get_json(url):
    with urllib.request.urlopen(url, timeout=60) as fh:
        return json.load(fh)


def _download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with urllib.request.urlopen(url, timeout=300) as src, open(tmp, "wb") as out:
        while True:
            chunk = src.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
    os.replace(tmp, dest)
    return True


def fetch_texture(key, slug, res):
    try:
        files = _get_json("{}/files/{}".format(API, slug))
    except Exception as exc:
        print("  !! {:14s} {} -> {}".format(key, slug, exc))
        return 0
    got = 0
    for api_map, local in WANTED.items():
        node = files.get(api_map)
        if not node:
            continue
        entry = node.get(res) or node.get("2k") or node.get("1k")
        if not entry:
            continue
        info = entry.get("jpg") or entry.get("png") or next(iter(entry.values()))
        url = info.get("url") if isinstance(info, dict) else None
        if not url:
            continue
        ext = os.path.splitext(url)[1] or ".jpg"
        dest = os.path.join(TEX_DIR, key, local + ext)
        try:
            if _download(url, dest):
                got += 1
        except Exception as exc:
            print("  !! {} {} -> {}".format(key, local, exc))
    print("  {:14s} {:28s} {} maps".format(key, slug, got if got else "cached/none"))
    return got


def fetch_hdri(res="2k"):
    try:
        files = _get_json("{}/files/{}".format(API, HDRI))
        entry = files["hdri"][res]["hdr"]
        dest = os.path.join(HDRI_DIR, HDRI + "_" + res + ".hdr")
        _download(entry["url"], dest)
        print("  hdri           {:28s} ok".format(HDRI))
        return dest
    except Exception as exc:
        print("  !! hdri {} -> {}".format(HDRI, exc))
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="2k")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    print("Poly Haven CC0 assets -> {}".format(os.path.join(HERE, "assets")))
    total = 0
    for key, slug in TEXTURES.items():
        if only and key not in only:
            continue
        total += fetch_texture(key, slug, args.res)
    if not only or "hdri" in only:
        fetch_hdri(args.res)
    print("downloaded {} new map files".format(total))


if __name__ == "__main__":
    sys.exit(main())
