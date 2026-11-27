"""Property test for the T-003 facade helpers in buildings_core.py.

Checks, over 3000 random facades across every style, that

  * _bay_plan() always returns one bay per column, inside the facade, with at
    least 0.25 m between neighbouring window frames (no collisions);
  * _ribbon_plan() segments stay inside the facade and keep a >= 0.29 m pier.

Run (needs Blender because buildings_core imports bpy):

    blender -b -P tools/test_facade_rhythm.py

Exits non-zero if any case fails.
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import buildings_core as B  # noqa: E402


def main():
    problems = []
    rhythms = set()
    for seed in range(3000):
        R = random.Random(seed)
        length = R.uniform(8, 60)
        style = R.choice(sorted(B.STYLES))
        st = B.STYLES[style]
        cols = max(1, int(length // (st["cols"] * R.uniform(0.86, 1.18))))
        ww = st["win_w"] * R.uniform(0.84, 1.22)
        rhythm = R.choice(B.RHYTHMS)
        rhythms.add(rhythm)
        bays = B._bay_plan(length, cols, ww, rhythm, R.randint(1, 12), R)
        if len(bays) != cols:
            problems.append(("bay count", seed))
        prev_edge = None
        for s, wm, _stair in bays:
            lo, hi = s - ww * wm / 2, s + ww * wm / 2
            if lo < -length / 2 - 1e-6 or hi > length / 2 + 1e-6:
                problems.append(("outside facade", seed, style, rhythm))
            if prev_edge is not None and (lo - 0.08) - prev_edge < 0.25:
                problems.append(("frames collide", seed, style, rhythm))
            prev_edge = hi + 0.08
        ribbon = B._ribbon_plan(length, R)
        if ribbon:
            for s, w in ribbon:
                if s - w / 2 < -length / 2 or s + w / 2 > length / 2:
                    problems.append(("ribbon outside", seed))
            for a, b in zip(ribbon, ribbon[1:]):
                if (b[0] - b[1] / 2) - (a[0] + a[1] / 2) < 0.29:
                    problems.append(("ribbon piers", seed))
    print("rhythms exercised:", sorted(rhythms))
    print("problems:", len(problems))
    for p in problems[:10]:
        print("  ", p)
    if problems:
        sys.exit(1)


main()
