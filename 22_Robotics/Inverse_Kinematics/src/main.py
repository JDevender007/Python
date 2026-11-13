"""Command line entry point for the Inverse Kinematics project.

Usage
-----
    python src/main.py --demo
    python src/main.py --target "1.0,0.8" --arm planar2
    python src/main.py --target "1.0,0.5,45" --arm planar3 --method dls
    python src/main.py --targets data/targets.csv --json solutions.json
    python src/main.py --targets data/targets.csv --quiet

Fully offline: arm definitions in local JSON, targets in a local CSV or
on the command line. No network, no API keys, no ROS, no hardware.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import math
import sys
from pathlib import Path

from ik import (
    DEMO_ARMS,
    DEMO_TARGETS,
    ELBOWS,
    METHODS,
    IkError,
    load_arms,
    load_targets,
    parse_target,
    parse_values,
    render_solution,
    render_table,
    run_demo,
    select_arm,
    solve,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("ik")

BANNER = """
========================================
 INVERSE KINEMATICS
   analytic 2R + damped least squares
   offline, deterministic
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Solve inverse kinematics for planar arms (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run the bundled targets demo")
    action.add_argument("--targets", type=Path, default=None,
                        help="target CSV (default: bundled sample)")
    action.add_argument("--target", default=None,
                        help="single target 'x,y' or 'x,y,yaw'")
    parser.add_argument("--file", type=Path, default=None,
                        help="arms JSON file (default: bundled sample)")
    parser.add_argument("--arm", default=None,
                        help="arm name inside --file (default: first)")
    parser.add_argument("--method", choices=METHODS, default="auto",
                        help="solver to use (default: auto)")
    parser.add_argument("--elbow", choices=ELBOWS, default="up",
                        help="elbow branch for the analytic solver")
    parser.add_argument("--q0", default=None,
                        help="initial joint values for dls, e.g. '10,10'")
    parser.add_argument("--damping", type=float, default=0.05,
                        help="dls damping factor (default 0.05)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the solution(s) as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def _solve_with(arm, target, args) -> object:
    kwargs = {}
    if args.q0 is not None:
        kwargs["q0"] = parse_values(args.q0)
    if not math.isfinite(args.damping) or args.damping <= 0:
        raise IkError(f"damping must be > 0, got {args.damping}")
    kwargs["damping"] = args.damping
    return solve(arm, target, method=args.method, elbow=args.elbow, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except IkError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.targets is None and args.target is None:
        parser.error("one of the arguments --demo --targets --target is "
                     "required")

    # fast-fail: validate the single target and damping before file I/O
    target_values = None
    if args.target is not None:
        try:
            target_values = parse_target(args.target)
        except IkError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
    if args.damping <= 0:
        print(f"Error: damping must be > 0, got {args.damping}",
              file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)

    try:
        arms = load_arms(args.file or DEMO_ARMS)
        if target_values is not None:
            arm = select_arm(arms, args.arm)
            solution = _solve_with(arm, target_values, args)
            rows = [(f"({target_values[0]:.2f},{target_values[1]:.2f})",
                     solution)]
            payload = {"solutions": [solution.to_dict()]}
        else:
            targets = load_targets(args.targets or DEMO_TARGETS, arms)
            rows = []
            payload = {"solutions": []}
            for target in targets:
                solution = _solve_with(arms[target.arm], target.values, args)
                rows.append((target.name, solution))
                payload["solutions"].append(solution.to_dict())
    except IkError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print()
        print(render_table(rows))
        for label, solution in rows[:2]:
            print()
            print(render_solution(solution, arms[solution.arm]))

    if args.json:
        payload["arms"] = list(arms)
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
