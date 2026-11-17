"""Command line entry point for the Forward Kinematics project.

Usage
-----
    python src/main.py --demo                          # bundled demo
    python src/main.py --angles "45,-90"               # default (first) arm
    python src/main.py --file data/arms.json --arm planar2 --angles "0,0"
    python src/main.py --file data/arms.json --json pose.json

Fully offline: arm definitions in local JSON, scenarios in a local CSV.
No network, no API keys, no ROS, no hardware.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from fk import (
    DEMO_ARMS,
    FkError,
    end_effector,
    limit_statuses,
    load_arms,
    parse_angles,
    reach_status,
    render_report,
    run_demo,
    select_arm,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("fk")

BANNER = """
========================================
 FORWARD KINEMATICS
   DH-parameter arms, offline
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
        description="Joint angles -> end-effector pose via DH parameters "
                    "(offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run the bundled scenarios demo")
    action.add_argument("--file", type=Path, default=None,
                        help="arms JSON file (default: bundled sample)")
    parser.add_argument("--arm", default=None,
                        help="arm name inside --file (default: first)")
    parser.add_argument("--angles", default=None,
                        help="comma-separated joint values: degrees for "
                             "revolute joints, metres for prismatic")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the pose report as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except FkError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.file is None and args.angles is None:
        parser.error("one of the arguments --demo --file --angles is "
                     "required")

    # fast-fail: validate angle syntax before touching any file
    q = None
    if args.angles is not None:
        try:
            q = parse_angles(args.angles)
        except FkError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if not args.quiet:
        print(BANNER)
    try:
        arms = load_arms(args.file or DEMO_ARMS)
        arm = select_arm(arms, args.arm)
        values = q if q is not None else [0.0] * arm.n_joints
        pose = end_effector(arm, values)
        statuses = limit_statuses(arm, values)
        reach = reach_status(arm, pose)
    except FkError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(arm, values, pose))

    if args.json:
        payload = {
            "arm": arm.name,
            "angles": [round(float(v), 6) for v in values],
            "pose": pose.to_dict(),
            "limit_statuses": [state for _, state, _ in statuses],
            "reach": {"status": reach[0], "distance": round(reach[1], 6),
                      "inner": round(reach[2], 6),
                      "outer": round(reach[3], 6)},
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
