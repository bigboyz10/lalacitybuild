#!/usr/bin/env python3
"""Download the raw CC0 model library from Poly Haven.

Usage:  python3 tools/fetch_models.py [--res 1k] [--only k1,k2] [--tag tree]

Raw scans are big (a single tree is 60-200 MB) and land in assets/raw/, which
is gitignored.  Run tools/build_library.py afterwards to decimate them into the
compact, committed assets/lib/*.glb that the city actually loads.
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import MODELS, by_tag

API = "https://api.polyhaven.com"
UA = {"User-Agent": "lalacitybuild/1.0 (Blender city generator)"}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(HERE, "assets", "raw")


def _get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as fh:
        return json.load(fh)


def _download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 256:
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers=UA)
    total = 0
    with urllib.request.urlopen(req, timeout=900) as src, open(tmp, "wb") as out:
        while True:
            chunk = src.read(1 << 18)
            if not chunk:
                break
            out.write(chunk)
            total += len(chunk)
    os.replace(tmp, dest)
    return total


def fetch(key, spec, res):
    slug = spec["slug"]
    try:
        files = _get_json("{}/files/{}".format(API, slug))
        entry = files["gltf"][res]["gltf"]
    except Exception as exc:
        print("  !! {:18s} {:28s} {}".format(key, slug, exc), flush=True)
        return 0
    folder = os.path.join(RAW_DIR, key)
    got = 0
    try:
        got += _download(entry["url"], os.path.join(folder, slug + "_" + res + ".gltf"))
        for rel, info in entry.get("include", {}).items():
            got += _download(info["url"], os.path.join(folder, rel.replace("/", os.sep)))
    except Exception as exc:
        print("  !! {:18s} {}".format(key, exc), flush=True)
        return 0
    print("  {:18s} {:28s} {:>9}".format(
        key, slug, "cached" if got == 0 else "{:.1f} MB".format(got / 1e6)), flush=True)
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="1k")
    ap.add_argument("--only", default="")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    keys = list(MODELS)
    if args.tag:
        keys = by_tag(args.tag)
    if args.only:
        want = [s.strip() for s in args.only.split(",") if s.strip()]
        keys = [k for k in keys if k in want]

    print("raw models -> {}  ({} assets)".format(RAW_DIR, len(keys)), flush=True)
    total = 0
    for key in keys:
        total += fetch(key, MODELS[key], args.res)
    print("downloaded {:.1f} MB".format(total / 1e6), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
