#!/usr/bin/env python3
"""Deterministic regression harness for the city build  (board task T-012).

Why this exists
---------------
A module can crash and the build still exits 0. That is not hypothetical: a
missing `GROUND_H` import once took out the whole buildings pass, and the run
reported success with a city that had no buildings in it. Exit status alone is
not a signal, so this harness asserts on what was actually produced.

Checks, per look (`la` and `nyc`):
  1. the process exits 0
  2. no module printed a `!!` failure line
  3. every collection that must exist does, and is non-empty
  4. object and triangle totals land inside recorded bands
  5. the same seed twice produces byte-identical counts (determinism)

Usage
-----
  python3 tools/regress.py                 # run the suite
  python3 tools/regress.py --update        # re-record the baseline
  python3 tools/regress.py --size 200      # smaller/faster
  python3 tools/regress.py --look la       # one look only
  python3 tools/regress.py --quick         # skip the determinism re-run

Exit codes:  0 pass, 1 regression, 2 harness/toolchain error.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(HERE, "tools", "regress_baseline.json")

# Collections that must be present and non-empty in any healthy build.
# Keep this conservative: things that are legitimately look-dependent live in
# LOOK_REQUIRED instead.
REQUIRED = [
    "CITY_Terrain",
    "CITY_Roads",
    "CITY_Sidewalks",
    "CITY_Buildings",
    "CITY_Roofs",
    "CITY_Props",
    "CITY_Utilities",
    "CITY_Vehicles",
    "CITY_Vegetation",
    "CITY_People",
]
LOOK_REQUIRED = {
    "la": [],
    "nyc": [],
}

# Tolerance on totals. Procedural output shifts when a module is tuned, so the
# band is wide enough to allow real work and tight enough to catch a module
# dropping out entirely (which halves or quarters a count, not 15%).
TOLERANCE = 0.22

FAIL_RE = re.compile(r"^\s*!!\s*(.+)$", re.M)


def blender_bin():
    for cand in (os.environ.get("BLENDER"),
                 "/home/user/.local/bin/blender",
                 shutil.which("blender")):
        if cand and os.path.exists(cand):
            return cand
    return None


def run_build(look, size, seed, density, out_dir):
    """Run one headless build; return (ok, failures, report, stdout_tail)."""
    bl = blender_bin()
    if bl is None:
        return False, ["blender not found - run tools/setup_env.sh"], None, ""

    env = dict(os.environ)
    libs = "/home/user/.local/libs/usr/lib/x86_64-linux-gnu"
    if os.path.isdir(libs):
        env["LD_LIBRARY_PATH"] = libs + ":" + env.get("LD_LIBRARY_PATH", "")

    cmd = [bl, "-b", "-P", os.path.join(HERE, "master.py"), "--",
           "--size", str(size), "--seed", str(seed), "--density", str(density),
           "--look", look, "--no-render", "--no-blend", "--out", out_dir]
    try:
        proc = subprocess.run(cmd, cwd=HERE, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=3600)
    except subprocess.TimeoutExpired:
        return False, ["build timed out"], None, ""

    text = proc.stdout.decode("utf-8", "replace")
    failures = [m.strip() for m in FAIL_RE.findall(text)]
    if proc.returncode != 0:
        failures.append("blender exited {}".format(proc.returncode))

    report = None
    path = os.path.join(out_dir, "city_report.json")
    if os.path.exists(path):
        try:
            with open(path) as fh:
                report = json.load(fh)
        except Exception as exc:
            failures.append("unreadable city_report.json: {}".format(exc))
    else:
        failures.append("no city_report.json was written")

    return (not failures), failures, report, text[-1500:]


def summarise(report):
    cols = report.get("collections", {})
    return {
        "objects": report.get("objects", 0),
        "triangles": report.get("triangles", 0),
        "collections": {k: v.get("objects", 0) for k, v in cols.items()},
    }


def check_bands(name, got, want, problems):
    for key in ("objects", "triangles"):
        g, w = got[key], want.get(key, 0)
        if w <= 0:
            continue
        lo, hi = w * (1 - TOLERANCE), w * (1 + TOLERANCE)
        if not (lo <= g <= hi):
            problems.append(
                "{}: {} = {:,} outside band {:,}..{:,} (baseline {:,})".format(
                    name, key, g, int(lo), int(hi), w))


def check_required(look, got, problems):
    cols = got["collections"]
    for want in REQUIRED + LOOK_REQUIRED.get(look, []):
        if cols.get(want, 0) <= 0:
            problems.append(
                "{}: collection {} is missing or empty - a module likely "
                "crashed without failing the build".format(look, want))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=240)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--density", type=float, default=0.8)
    ap.add_argument("--look", default="", help="la | nyc (default: both)")
    ap.add_argument("--update", action="store_true", help="re-record baseline")
    ap.add_argument("--quick", action="store_true", help="skip determinism re-run")
    args = ap.parse_args()

    looks = [args.look] if args.look else ["la", "nyc"]

    baseline = {}
    if os.path.exists(BASELINE):
        with open(BASELINE) as fh:
            baseline = json.load(fh)

    results, problems = {}, []
    print("regression harness  size={} seed={} density={}".format(
        args.size, args.seed, args.density))

    for look in looks:
        tmp = tempfile.mkdtemp(prefix="regress_{}_".format(look))
        print("\n--- {} ---".format(look))
        ok, failures, report, tail = run_build(
            look, args.size, args.seed, args.density, tmp)

        if not ok or report is None:
            for f in failures:
                problems.append("{}: {}".format(look, f))
            print("  BUILD FAILED")
            for f in failures[:8]:
                print("    !! {}".format(f))
            if tail and not blender_bin():
                print(tail)
            shutil.rmtree(tmp, ignore_errors=True)
            continue

        got = summarise(report)
        results[look] = got
        print("  objects {:,}   triangles {:,}   collections {}".format(
            got["objects"], got["triangles"], len(got["collections"])))

        check_required(look, got, problems)

        key = "{}@{}".format(look, args.size)
        if not args.update and key in baseline:
            check_bands(look, got, baseline[key], problems)
        elif not args.update:
            print("  (no baseline for {} - run --update to record)".format(key))

        # determinism: identical seed must give identical counts
        if not args.quick:
            tmp2 = tempfile.mkdtemp(prefix="regress_{}_b_".format(look))
            ok2, _f2, rep2, _t2 = run_build(
                look, args.size, args.seed, args.density, tmp2)
            if ok2 and rep2:
                got2 = summarise(rep2)
                if got2 != got:
                    diff = [k for k in ("objects", "triangles") if got2[k] != got[k]]
                    problems.append(
                        "{}: NOT DETERMINISTIC - same seed differed in {}"
                        .format(look, ", ".join(diff) or "collections"))
                else:
                    print("  deterministic: identical on re-run")
            shutil.rmtree(tmp2, ignore_errors=True)

        shutil.rmtree(tmp, ignore_errors=True)

    if args.update:
        for look, got in results.items():
            baseline["{}@{}".format(look, args.size)] = {
                "objects": got["objects"],
                "triangles": got["triangles"],
                "collections": got["collections"],
            }
        with open(BASELINE, "w") as fh:
            json.dump(baseline, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("\nbaseline written to {}".format(os.path.relpath(BASELINE, HERE)))
        return 0

    print("\n" + "=" * 68)
    if problems:
        print("REGRESSIONS ({})".format(len(problems)))
        for p in problems:
            print("  - {}".format(p))
        print("=" * 68)
        return 1
    if not results:
        print("NOTHING RAN - toolchain problem")
        print("=" * 68)
        return 2
    print("PASS - {} look(s) built clean and within band".format(len(results)))
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
