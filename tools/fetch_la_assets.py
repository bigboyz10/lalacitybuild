#!/usr/bin/env python3
"""Download Los-Angeles-flavoured CC0 PBR textures from Poly Haven.

Usage:
    python3 tools/fetch_la_assets.py --list            # show what it would pick, download nothing
    python3 tools/fetch_la_assets.py --res 2k          # download

Why a keyword search instead of fixed slugs: Poly Haven renames and retires
assets, so a hard-coded slug can quietly 404. Here each LA material is described
by a few keywords; the script asks the Poly Haven API for every texture,
scores them against the keywords and takes the best match. Run --list first to
see (and veto) the picks. Everything on Poly Haven is CC0.

It reuses the download code from tools/fetch_assets.py, so files land in
assets/textures/<key>/ exactly like the originals and re-runs skip what exists.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_assets as FA  # noqa: E402

# local texture-set key -> (keywords in order of importance, keywords to avoid)
LA_TEXTURES = {
    "stucco":      (["stucco", "plaster", "rough_plaster", "painted_plaster", "wall"],
                    ["brick", "tile", "wood", "floor", "marble", "stone_brick"]),
    "roof_tile":   (["roof_tiles", "roof tile", "terracotta", "clay", "tiles"],
                    ["floor", "wall_tiles", "ceramic", "bathroom"]),
    "dry_ground":  (["dry", "sand", "dirt", "gravel", "desert"],
                    ["snow", "wet", "mud", "rock_wall"]),
    "asphalt_la":  (["asphalt", "road", "tarmac"],
                    ["wet", "cracked_wall"]),
    "concrete_la": (["concrete", "cement", "wall"],
                    ["floor_tiles", "brick"]),
    "palm_bark":   (["palm_tree_bark", "palm", "bark"],
                    ["leaf", "leaves", "moss", "floor"]),
    "stucco_paint": (["painted_plaster", "painted", "plaster", "wall"],
                     ["brick", "tile", "wood", "floor", "stone_brick"]),
}


def score(slug, info, include, exclude):
    hay = " ".join([slug, str(info.get("name", ""))] +
                   [str(t) for t in info.get("tags", [])] +
                   [str(c) for c in info.get("categories", [])]).lower().replace("-", "_")
    s = 0.0
    for rank, kw in enumerate(include):
        if kw.lower().replace(" ", "_") in hay or kw.lower() in hay:
            s += 10.0 / (1 + rank)
    for kw in exclude:
        if kw.lower() in hay:
            s -= 6.0
    # tie-break on popularity so well-made, well-used scans win
    s += min(3.0, (info.get("download_count") or 0) / 100000.0)
    return s


def pick(assets, include, exclude, taken):
    ranked = sorted(((score(slug, info, include, exclude), slug)
                     for slug, info in assets.items() if slug not in taken),
                    reverse=True)
    return ranked[0] if ranked and ranked[0][0] > 0 else (0.0, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="2k")
    ap.add_argument("--list", action="store_true", help="only show the picks")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    print("Asking Poly Haven for its texture list ...")
    assets = FA._get_json("{}/assets?t=textures".format(FA.API))
    print("  {} textures on Poly Haven\n".format(len(assets)))

    taken = set(FA.TEXTURES.values())     # do not re-pick what the base set uses
    total = 0
    for key, (inc, exc) in LA_TEXTURES.items():
        if only and key not in only:
            continue
        sc, slug = pick(assets, inc, exc, taken)
        if not slug:
            print("  {:12s} no match for {}".format(key, inc))
            continue
        taken.add(slug)
        print("  {:12s} -> {:32s} (score {:.1f})".format(key, slug, sc))
        if not args.list:
            total += FA.fetch_texture(key, slug, args.res)
    if args.list:
        print("\n--list only: nothing downloaded. Drop --list to fetch.")
    else:
        print("\ndownloaded {} new map files into {}".format(total, FA.TEX_DIR))


if __name__ == "__main__":
    sys.exit(main())
