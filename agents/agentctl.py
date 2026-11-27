#!/usr/bin/env python3
"""agentctl - coordination for several AI agents sharing one repo.

Why it exists
-------------
Five agents in five sandboxes cannot see each other. The only thing they share
is the GitHub remote, so the remote is the coordination medium. `main` holds a
board; each agent works on its own branch and never pushes code to `main`.

Claiming is atomic because git ref updates are atomic: an agent reads the board
from the remote, edits it, and pushes. If another agent got there first the
push is rejected as non-fast-forward, and we retry on the new state. Exactly
one agent can win a claim.

Board operations run in a private clone (~/.agent-board) so an agent's dirty
working tree is never touched.

Usage
-----
  python3 agents/agentctl.py whoami
  python3 agents/agentctl.py status
  python3 agents/agentctl.py claim [--area trees.py] [--size S]
  python3 agents/agentctl.py note T-003 "found the jitter hook"
  python3 agents/agentctl.py heartbeat
  python3 agents/agentctl.py handoff T-003 "stopped at 60%: see notes"
  python3 agents/agentctl.py done T-003 "merged to agent branch, tests pass"
  python3 agents/agentctl.py release-stale
"""
import argparse
import datetime as dt
import json
import os
import random
import socket
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_REL = "agents/board.json"
WORK = os.path.expanduser("~/.agent-board")
ORIGIN = "https://github.com/bigboyz10/lalacitybuild.git"
MAX_RETRY = 8


def sh(args, cwd=None, check=True, quiet=True):
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError("{}\n{}".format(" ".join(args), res.stderr.strip()))
    if not quiet and res.stdout.strip():
        print(res.stdout.strip())
    return res


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(ts):
    if not ts:
        return None
    try:
        return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def agent_id():
    """Stable identity for this agent: AGENT_ID env, else host-based."""
    env = os.environ.get("AGENT_ID")
    if env:
        return env.strip()
    path = os.path.expanduser("~/.agent-id")
    if os.path.exists(path):
        return open(path).read().strip()
    ident = "agent-{}-{}".format(socket.gethostname()[:8], random.randint(100, 999))
    with open(path, "w") as fh:
        fh.write(ident)
    return ident


def origin_url():
    try:
        res = sh(["git", "remote", "get-url", "origin"], cwd=REPO)
        return res.stdout.strip() or ORIGIN
    except Exception:
        return ORIGIN


def ensure_clone():
    """A private clone used only for board edits."""
    if not os.path.isdir(os.path.join(WORK, ".git")):
        os.makedirs(os.path.dirname(WORK), exist_ok=True)
        sh(["git", "clone", "--depth", "50", "-b", "main", origin_url(), WORK])
        sh(["git", "config", "user.name", "agentctl"], cwd=WORK)
        sh(["git", "config", "user.email", "agentctl@localhost"], cwd=WORK)
    return WORK


def refresh():
    ensure_clone()
    sh(["git", "fetch", "-q", "origin", "main"], cwd=WORK)
    sh(["git", "reset", "-q", "--hard", "origin/main"], cwd=WORK)
    path = os.path.join(WORK, BOARD_REL)
    if not os.path.exists(path):
        raise SystemExit("No {} on main yet - push the board first.".format(BOARD_REL))
    with open(path) as fh:
        return json.load(fh)


def commit_push(board, message):
    path = os.path.join(WORK, BOARD_REL)
    board["updated"] = iso(now())
    with open(path, "w") as fh:
        json.dump(board, fh, indent=2)
        fh.write("\n")
    sh(["git", "add", BOARD_REL], cwd=WORK)
    res = sh(["git", "commit", "-q", "-m", message], cwd=WORK, check=False)
    if res.returncode != 0 and "nothing to commit" in (res.stdout + res.stderr):
        return True
    push = sh(["git", "push", "-q", "origin", "HEAD:main"], cwd=WORK, check=False)
    return push.returncode == 0


def transaction(mutate, message):
    """Read-modify-write the board, retrying when another agent wins the race."""
    for attempt in range(MAX_RETRY):
        board = refresh()
        result = mutate(board)
        if result is None:
            return None
        if commit_push(board, message):
            return result
        time.sleep(0.4 + random.random() * 0.8 * (attempt + 1))
    raise SystemExit("Could not update the board after {} attempts.".format(MAX_RETRY))


def lease_active(task, minutes):
    until = parse(task.get("lease_until"))
    return until is not None and until > now()


def fmt_task(t):
    owner = t.get("owner") or "-"
    lease = t.get("lease_until") or ""
    return "  {:6s} {:9s} {:14s} {:3s} p{}  {}{}".format(
        t["id"], t["status"], owner[:14], t.get("size", "?"), t.get("priority", 9),
        t["title"][:58], "  (lease {})".format(lease) if lease else "")


# ---------------------------------------------------------------- commands
def cmd_whoami(_):
    print(agent_id())


def cmd_status(args):
    board = refresh()
    mins = board.get("lease_minutes", 45)
    print("board updated {}   lease {} min".format(board.get("updated"), mins))
    buckets = {}
    for t in board["tasks"]:
        buckets.setdefault(t["status"], []).append(t)
    for status in ("claimed", "review", "todo", "blocked", "done"):
        rows = buckets.get(status, [])
        if not rows:
            continue
        print("\n{} ({})".format(status.upper(), len(rows)))
        for t in sorted(rows, key=lambda x: (x.get("priority", 9), x["id"])):
            stale = (t["status"] == "claimed" and not lease_active(t, mins))
            print(fmt_task(t) + ("   <- LEASE EXPIRED, reclaimable" if stale else ""))
    if args.verbose:
        print("\nnotes:")
        for t in board["tasks"]:
            for n in t.get("notes", []):
                print("  {} {}: {}".format(t["id"], n.get("by", "?"), n.get("text", "")))


def _ready(task, board):
    done_ids = {t["id"] for t in board["tasks"] if t["status"] == "done"}
    return all(d in done_ids for d in task.get("depends_on", []))


def cmd_claim(args):
    me = agent_id()
    mins = None

    def mutate(board):
        nonlocal mins
        mins = board.get("lease_minutes", 45)
        # already holding something? return it rather than double-claiming
        for t in board["tasks"]:
            if t["status"] == "claimed" and t.get("owner") == me and lease_active(t, mins):
                print("Already holding {} - {}".format(t["id"], t["title"]))
                return None
        pool = []
        for t in board["tasks"]:
            if t["status"] == "todo" or (t["status"] == "claimed" and not lease_active(t, mins)):
                if not _ready(t, board):
                    continue
                if args.area and not any(args.area in a for a in t.get("area", [])):
                    continue
                if args.size and t.get("size") != args.size:
                    continue
                pool.append(t)
        if not pool:
            print("Nothing claimable right now.")
            return None
        pool.sort(key=lambda t: (t.get("priority", 9), t["id"]))
        task = pool[0]
        reclaimed = task["status"] == "claimed"
        task["status"] = "claimed"
        task["owner"] = me
        task["branch"] = "agent/{}/{}".format(me, task["id"].lower())
        task["lease_until"] = iso(now() + dt.timedelta(minutes=mins))
        task.setdefault("notes", []).append({
            "by": me, "at": iso(now()),
            "text": "reclaimed after expired lease" if reclaimed else "claimed"})
        board.setdefault("agents", {})[me] = {"last_seen": iso(now()), "task": task["id"]}
        return task

    task = transaction(mutate, "board: claim by {}".format(me))
    if task:
        print("Claimed {}  {}".format(task["id"], task["title"]))
        print("  branch : {}".format(task["branch"]))
        print("  lease  : {} minutes (run 'heartbeat' to extend)".format(mins))
        print("  area   : {}".format(", ".join(task.get("area", []))))
        print("\n  {}".format(task.get("detail", "")))


def _find(board, task_id):
    for t in board["tasks"]:
        if t["id"].lower() == task_id.lower():
            return t
    return None


def cmd_note(args):
    me = agent_id()

    def mutate(board):
        t = _find(board, args.task)
        if not t:
            raise SystemExit("No such task: {}".format(args.task))
        t.setdefault("notes", []).append({"by": me, "at": iso(now()), "text": args.text})
        return t
    transaction(mutate, "board: note on {} by {}".format(args.task, me))
    print("noted on {}".format(args.task))


def cmd_heartbeat(args):
    me = agent_id()

    def mutate(board):
        mins = board.get("lease_minutes", 45)
        touched = []
        for t in board["tasks"]:
            if t["status"] == "claimed" and t.get("owner") == me:
                t["lease_until"] = iso(now() + dt.timedelta(minutes=mins))
                touched.append(t["id"])
        board.setdefault("agents", {})[me] = {"last_seen": iso(now()),
                                              "task": touched[0] if touched else None}
        if not touched:
            print("No claimed tasks to refresh.")
            return None
        return touched
    out = transaction(mutate, "board: heartbeat {}".format(me))
    if out:
        print("lease extended for {}".format(", ".join(out)))


def cmd_handoff(args):
    """Release a task but keep every note, so the next agent resumes mid-stream."""
    me = agent_id()

    def mutate(board):
        t = _find(board, args.task)
        if not t:
            raise SystemExit("No such task: {}".format(args.task))
        t["status"] = "todo"
        t["owner"] = None
        t["lease_until"] = None
        t.setdefault("notes", []).append({
            "by": me, "at": iso(now()),
            "text": "HANDOFF: " + (args.text or "released"),
            "branch": t.get("branch")})
        return t
    transaction(mutate, "board: handoff {} from {}".format(args.task, me))
    print("{} released with handoff notes - any agent can pick it up".format(args.task))


def cmd_done(args):
    me = agent_id()

    def mutate(board):
        t = _find(board, args.task)
        if not t:
            raise SystemExit("No such task: {}".format(args.task))
        t["status"] = "review" if not args.merged else "done"
        t["lease_until"] = None
        t.setdefault("notes", []).append({
            "by": me, "at": iso(now()), "text": args.text or "completed"})
        return t
    transaction(mutate, "board: {} {} by {}".format(
        "done" if args.merged else "review", args.task, me))
    print("{} -> {}".format(args.task, "done" if args.merged else "review"))


def cmd_release_stale(args):
    def mutate(board):
        mins = board.get("lease_minutes", 45)
        freed = []
        for t in board["tasks"]:
            if t["status"] == "claimed" and not lease_active(t, mins):
                t.setdefault("notes", []).append({
                    "by": "agentctl", "at": iso(now()),
                    "text": "lease expired, released from {}".format(t.get("owner"))})
                t["status"] = "todo"
                t["owner"] = None
                t["lease_until"] = None
                freed.append(t["id"])
        if not freed:
            print("No stale leases.")
            return None
        return freed
    out = transaction(mutate, "board: release stale leases")
    if out:
        print("released {}".format(", ".join(out)))


def main():
    ap = argparse.ArgumentParser(description="Multi-agent board for lalacitybuild")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)

    p = sub.add_parser("status"); p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("claim")
    p.add_argument("--area", help="only tasks touching this file/area")
    p.add_argument("--size", choices=["S", "M", "L"])
    p.set_defaults(fn=cmd_claim)

    p = sub.add_parser("note"); p.add_argument("task"); p.add_argument("text")
    p.set_defaults(fn=cmd_note)

    sub.add_parser("heartbeat").set_defaults(fn=cmd_heartbeat)

    p = sub.add_parser("handoff"); p.add_argument("task")
    p.add_argument("text", nargs="?", default="")
    p.set_defaults(fn=cmd_handoff)

    p = sub.add_parser("done"); p.add_argument("task")
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--merged", action="store_true", help="already merged into main")
    p.set_defaults(fn=cmd_done)

    sub.add_parser("release-stale").set_defaults(fn=cmd_release_stale)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
