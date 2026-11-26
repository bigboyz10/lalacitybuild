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
UA = {"User-Agent": "lalacitybuild/1.0 (Blender city generator; contact: local)"}
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
    "stone_old":      "cobblestone_floor_01",
    "metal_dark":     "metal_plate",
    "rust":           "rusty_metal_sheet",
    "roof_tar":       "grey_roof_tiles",
    "grass":          "aerial_grass_rock",
    "tiles_floor":    "floor_tiles_06",
}

# Poly Haven map key -> local filename. Alternatives are tried in order.
WANTED = {
    "diffuse":   ["Diffuse", "diff", "albedo", "Color"],
    "roughness": ["Rough", "rough"],
    "normal":    ["nor_gl", "nor_dx"],
    "ao":        ["AO", "ao"],
    "displacement": ["Displacement", "disp"],
}

HDRI = "kloppenheim_06_puresky"


def _get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def _download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as src, open(tmp, "wb") as out:
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
    for local, candidates in WANTED.items():
        node = None
        for cand in candidates:
            if cand in files:
                node = files[cand]
                break
        if not node:
            continue
        entry = node.get(res) or node.get("2k") or node.get("1k")
        if not entry:
            continue
        info = entry.get("jpg") or entry.get("png")
        if not isinstance(info, dict) or not info.get("url"):
            continue
        url = info["url"]
        ext = os.path.splitext(url)[1] or ".jpg"
        dest = os.path.join(TEX_DIR, key, local + ext)
        try:
            if _download(url, dest):
                got += 1
        except Exception as exc:
            print("  !! {} {} -> {}".format(key, local, exc))
    have = len(os.listdir(os.path.join(TEX_DIR, key))) if os.path.isdir(os.path.join(TEX_DIR, key)) else 0
    print("  {:14s} {:28s} +{} new, {} maps on disk".format(key, slug, got, have))
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
