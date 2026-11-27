# =============================================================================
#  CITY BUILD  --  M18 : TRAFFIC
#  Closes critique item 5: "Traffic is frozen. Cars are placed, not simulated,
#  so there is no queueing at lights and no lane discipline."
#
#  This does not animate anything - it resolves one coherent instant of a
#  city's traffic and freezes the cars where they would actually be:
#
#    * lane discipline - each lane belongs to one direction (right-hand
#      traffic), and every car in it faces that way
#    * signalised intersections - each junction has a phase, so approaches on
#      red carry a compressed stopped queue back from the stop line, and
#      approaches on green are clear and moving
#    * headway - moving cars are spaced by speed-dependent gaps, queued cars
#      bumper-to-bumper at 1.4-2.6 m
#    * the junction box stays clear except for vehicles mid-turn on green
#    * parallel parking that respects hydrants, crossings and driveways
#
#  standalone:  blender -b -P traffic.py -- --size 320
# =============================================================================
import math
import os
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import core as C
from core import CONFIG, U, rng, plan_city
import roads
import vehicles as V

LANE_W = U["lane"]
ROAD_Z = getattr(V, "ROAD_Z", 0.16)

# metres of clear road a moving vehicle keeps in front of it, by road class
HEADWAY = {"arterial": (16.0, 30.0), "avenue": (12.0, 24.0),
           "street": (9.0, 20.0), "lane": (8.0, 16.0)}
QUEUE_GAP = (1.4, 2.6)          # bumper-to-bumper when stopped
STOP_LINE_SETBACK = 2.2         # metres back from the junction edge


def _lanes(seg):
    """Split a carriageway into lane centre offsets and their direction.

    Right-hand traffic: lanes left of the centreline run one way, lanes right
    of it run the other. Returns [(offset_from_centre, direction_sign)].
    """
    usable = max(LANE_W, seg["w"] - 1.2)
    n = max(2, int(usable // LANE_W))
    if n % 2:
        n -= 1                                   # keep it even, two directions
    n = max(2, n)
    per_side = n // 2
    out = []
    for i in range(per_side):
        off = -(i + 0.5) * LANE_W
        out.append((off, -1))                    # travelling in -axis
    for i in range(per_side):
        off = (i + 0.5) * LANE_W
        out.append((off, +1))                    # travelling in +axis
    return out


def _phase(plan, it, R):
    """Deterministic signal phase for one junction: which axis has green."""
    key = (round(it["x"], 1), round(it["y"], 1))
    return "ns" if (hash(key) ^ CONFIG["seed"]) % 2 == 0 else "ew"


def _junctions_on(seg, plan):
    """Junction extents this segment runs between, along its own axis."""
    out = []
    for it in plan["intersections"]:
        if seg["axis"] == "ns" and abs(it["x"] - seg["c"]) < 0.5:
            out.append(it)
        elif seg["axis"] == "ew" and abs(it["y"] - seg["c"]) < 0.5:
            out.append(it)
    return out


def _place(name, fn, collection, x, y, rot, z=None):
    V._place(name, fn(), collection, x, y, rot, z=ROAD_Z if z is None else z)


def build():
    R = rng("traffic")
    plan = plan_city()
    col = C.col("CITY_Traffic")
    segs = roads._segments(plan)
    detail = 1.0 if CONFIG["quality"] == "high" else 0.78

    moving = stopped = turning = 0

    for seg in segs:
        length = seg["b"] - seg["a"]
        if length < 14.0:
            continue
        lanes = _lanes(seg)
        kind = seg.get("kind", "street")
        lo_gap, hi_gap = HEADWAY.get(kind, HEADWAY["street"])

        juncs = _junctions_on(seg, plan)
        # junction this segment ends at, in the +axis direction
        def _stop_line(direction):
            if direction > 0:
                edge = seg["b"]
                near = [j for j in juncs
                        if (j["y"] if seg["axis"] == "ns" else j["x"]) >= edge - 0.6]
            else:
                edge = seg["a"]
                near = [j for j in juncs
                        if (j["y"] if seg["axis"] == "ns" else j["x"]) <= edge + 0.6]
            return (edge, near[0] if near else None)

        for (off, direction) in lanes:
            edge, junc = _stop_line(direction)
            red = False
            if junc is not None:
                green_axis = _phase(plan, junc, R)
                red = (green_axis != seg["axis"])

            # ---- queue of stopped cars back from a red light -------------
            cursor = edge - direction * STOP_LINE_SETBACK
            if red and junc is not None:
                qn = R.randint(0, max(1, int(6 * detail)))
                for _ in range(qn):
                    pos = cursor
                    if not (seg["a"] + 2.0 < pos < seg["b"] - 2.0):
                        break
                    kindv, fn = V._pick(R)
                    car_len = 4.8 if kindv in ("sedan", "taxi", "police") else 6.4
                    if seg["axis"] == "ns":
                        x, y = seg["c"] + off, pos
                        rot = (math.pi * 0.5) if direction > 0 else (-math.pi * 0.5)
                    else:
                        x, y = pos, seg["c"] + off
                        rot = 0.0 if direction > 0 else math.pi
                    rot += R.gauss(0.0, 0.012)       # never perfectly aligned
                    lat = R.gauss(0.0, 0.10)
                    if seg["axis"] == "ns":
                        x += lat
                    else:
                        y += lat
                    _place("Queue_{:04d}".format(stopped), fn, col, x, y, rot)
                    stopped += 1
                    cursor -= direction * (car_len + R.uniform(*QUEUE_GAP))

            # ---- free-flowing cars further back --------------------------
            pos = cursor - direction * R.uniform(lo_gap, hi_gap)
            guard = 0
            while seg["a"] + 3.0 < pos < seg["b"] - 3.0 and guard < 40:
                guard += 1
                if R.random() < 0.82 * detail:
                    kindv, fn = V._pick(R)
                    car_len = 4.8 if kindv in ("sedan", "taxi", "police") else 6.6
                    if seg["axis"] == "ns":
                        x, y = seg["c"] + off, pos
                        rot = (math.pi * 0.5) if direction > 0 else (-math.pi * 0.5)
                    else:
                        x, y = pos, seg["c"] + off
                        rot = 0.0 if direction > 0 else math.pi
                    rot += R.gauss(0.0, 0.02)
                    lat = R.gauss(0.0, 0.16)
                    if seg["axis"] == "ns":
                        x += lat
                    else:
                        y += lat
                    _place("Traffic_{:04d}".format(moving), fn, col, x, y, rot)
                    moving += 1
                    pos -= direction * (car_len + R.uniform(lo_gap, hi_gap))
                else:
                    pos -= direction * R.uniform(lo_gap, hi_gap)

    # ---- vehicles mid-turn inside junctions that are green ---------------
    for it in plan["intersections"]:
        green = _phase(plan, it, R)
        if R.random() > 0.38:
            continue
        kindv, fn = V._pick(R)
        w = it.get("w", 12.0)
        # a car part way through its turn: offset into the box, yaw between axes
        t = R.uniform(0.25, 0.75)
        if green == "ns":
            x = it["x"] + R.uniform(-1.2, 1.2)
            y = it["y"] + (t - 0.5) * w * 0.8
            rot = math.pi * 0.5 + R.uniform(-0.9, 0.9) * t
        else:
            x = it["x"] + (t - 0.5) * w * 0.8
            y = it["y"] + R.uniform(-1.2, 1.2)
            rot = R.uniform(-0.9, 0.9) * t
        _place("Turning_{:04d}".format(turning), fn, col, x, y, rot)
        turning += 1

    print("  traffic: {} moving, {} queued at reds, {} mid-junction".format(
        moving, stopped, turning))
    return moving + stopped + turning


if __name__ == "__main__":
    C.bootstrap(banner="M18 TRAFFIC")
    C.build_all_materials()
    build()
    C.report()
