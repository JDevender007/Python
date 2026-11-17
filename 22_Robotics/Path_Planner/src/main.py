"""Command line entry point for the Path Planner project.

Usage
-----
    python src/main.py --demo
    python src/main.py --map data/map.txt --algorithm astar
    python src/main.py --map data/map.txt --algorithm dijkstra --smooth
    python src/main.py --map data/map.txt --start "1,1" --goal "13,19"
    python src/main.py --map data/map.txt --json plan.json --quiet

Fully offline: the map is a local text file. No network, no API keys.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from planner import (
    ALGORITHMS,
    DEMO_MAP,
    HEURISTICS,
    Plan,
    PlannerError,
    find_path,
    load_map,
    parse_point,
    render_map,
    render_report,
    route_cost,
    run_demo,
    smooth_path,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("planner")

BANNER = """
========================================
 PATH PLANNER
   A*, Dijkstra, RRT, smoothing
   text maps, offline
========================================
"""


def _run_demo(quiet: bool, func, *args, **kwargs) -> int:
    """Run the offline demo; with --quiet no stream prints anything."""
    if not quiet:
        return func(*args, **kwargs)
    # --quiet: silence the demo's own prints and its log records alike, so a
    # scripted run writes nothing to stdout or stderr.
    level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(level)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan a path across a text occupancy grid (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run the bundled demo")
    action.add_argument("--map", type=Path, default=None,
                        help="map text file (default: bundled sample)")
    parser.add_argument("--algorithm", choices=ALGORITHMS, default="astar",
                        help="planner to use (default: astar)")
    parser.add_argument("--heuristic", choices=HEURISTICS, default="octile",
                        help="A* heuristic (default: octile)")
    parser.add_argument("--start", default=None,
                        help="override the start cell, e.g. '1,1'")
    parser.add_argument("--goal", default=None,
                        help="override the goal cell, e.g. '13,19'")
    parser.add_argument("--no-diagonal", dest="diagonal",
                        action="store_false", default=True,
                        help="4-connected movement only")
    parser.add_argument("--corner-cutting", action="store_true",
                        help="allow diagonal moves past blocked corners")
    parser.add_argument("--smooth", action="store_true",
                        help="shortcut the path with line-of-sight checks")
    parser.add_argument("--seed", type=int, default=7,
                        help="RRT random seed (default 7)")
    parser.add_argument("--step", type=int, default=3,
                        help="RRT extension step in cells (default 3)")
    parser.add_argument("--max-iters", type=int, default=3000,
                        help="RRT iteration budget (default 3000)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the plan as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except PlannerError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.map is None:
        parser.error("one of the arguments --demo --map is required")

    # fast-fail: coordinates and RRT flags before the map is read
    start = goal = None
    try:
        if args.start is not None:
            start = parse_point(args.start)
        if args.goal is not None:
            goal = parse_point(args.goal)
    except PlannerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.algorithm == "rrt" and not args.diagonal:
        print("Error: rrt always uses 8-connected movement", file=sys.stderr)
        return 2
    if args.algorithm == "rrt" and args.step < 1:
        print(f"Error: step must be >= 1, got {args.step}", file=sys.stderr)
        return 2
    if args.algorithm == "rrt" and args.max_iters < 1:
        print(f"Error: max_iters must be >= 1, got {args.max_iters}",
              file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)

    try:
        grid = load_map(args.map)
        kwargs = {"start": start, "goal": goal}
        if args.algorithm == "rrt":
            kwargs.update(seed=args.seed, step=args.step,
                          max_iters=args.max_iters)
        else:
            kwargs.update(diagonal=args.diagonal,
                          allow_corner_cutting=args.corner_cutting)
            if args.algorithm == "astar":
                kwargs["heuristic_name"] = args.heuristic
        plan = find_path(grid, args.algorithm, **kwargs)
        if args.smooth:
            route = smooth_path(grid, plan.path, args.corner_cutting)
            plan = Plan(f"{plan.algorithm}+smooth", route,
                        route_cost(route, args.diagonal), plan.expanded,
                        plan.heuristic)
    except PlannerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print()
        print(render_report(plan))
        print()
        print(render_map(grid, plan.path))

    if args.json:
        payload = {"map": grid.to_dict(), "plan": plan.to_dict()}
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
