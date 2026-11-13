"""Command line entry point for the Robot Arm Simulator project.

Usage
-----
    python src/main.py --demo
    python src/main.py --pose "0.6,0.4,45"
    python src/main.py --move "0.6,0.4,45" --to "0.3,0.7,90"
    python src/main.py --pose "0.6,0.4" --json pose.json
    python src/main.py --mission data/mission.json --json result.json

Fully offline: the arm and mission are local JSON files. No network, no
API keys, no ROS, no hardware.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from arm import (
    ARM_FILE,
    MISSION_FILE,
    ArmError,
    check_collisions,
    load_arm,
    load_mission,
    parse_pose,
    plan_cartesian_move,
    plan_joint_move,
    pose,
    render_report,
    run_demo,
    run_mission,
    solve_ik,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("arm")

BANNER = """
========================================
 ROBOT ARM SIMULATOR
   exact IK, min-jerk motion, missions
   offline, deterministic
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate a planar robot arm offline")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run the bundled pick-and-place demo")
    action.add_argument("--pose", default=None,
                        help="solve IK for 'x,y' or 'x,y,yaw'")
    action.add_argument("--mission", type=Path, default=None,
                        help="mission JSON file (default: bundled sample)")
    parser.add_argument("--move", default=None,
                        help="start configuration 'q0,q1[,q2]'")
    parser.add_argument("--to", default=None,
                        help="goal configuration 'q0,q1[,q2]'")
    parser.add_argument("--file", type=Path, default=None,
                        help="arm JSON file (default: bundled sample)")
    parser.add_argument("--cartesian", action="store_true",
                        help="with --move/--to treat --to as a pose")
    parser.add_argument("--steps", type=int, default=40,
                        help="Cartesian waypoints (default 40)")
    parser.add_argument("--dt", type=float, default=0.05,
                        help="trajectory sample period (default 0.05 s)")
    parser.add_argument("--speed-scale", type=float, default=1.0,
                        help="fraction of the joint speed limits (default 1)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the result as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def _render_trajectory(arm, trajectory, label: str) -> str:
    first = trajectory.samples[0]
    last = trajectory.samples[-1]
    speeds = ", ".join(f"{speed:.1f}" for speed in trajectory.max_speeds)
    return "\n".join([
        f"TRAJECTORY - {label}",
        "-" * 68,
        f"  samples    : {len(trajectory.samples)}",
        f"  duration   : {trajectory.duration:.3f} s",
        f"  dt         : {trajectory.dt:.4f} s",
        f"  start q    : "
        + ", ".join(f"{value:+.3f}" for value in first.q),
        f"  end q      : "
        + ", ".join(f"{value:+.3f}" for value in last.q),
        f"  start pose : ({first.x:+.4f}, {first.y:+.4f}) "
        f"yaw {first.yaw:+.2f}",
        f"  end pose   : ({last.x:+.4f}, {last.y:+.4f}) "
        f"yaw {last.yaw:+.2f}",
        f"  path length: {trajectory.cartesian_length:.4f} m",
        f"  peak speeds: {speeds} deg/s",
    ])


def _check_positive(parser: argparse.ArgumentParser, value: float,
                    label: str) -> float | None:
    if value <= 0 or value != value:
        print(f"Error: {label} must be > 0, got {value}", file=sys.stderr)
        return None
    return value


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
        except ArmError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.pose is None and args.mission is None and args.move is None:
        parser.error("one of the arguments --demo --pose --mission --move "
                     "is required")

    # fast-fail: numeric flags and poses before any file is read
    if _check_positive(parser, args.dt, "dt") is None:
        return 2
    if _check_positive(parser, args.speed_scale, "speed_scale") is None:
        return 2
    if isinstance(args.steps, bool) or args.steps < 2:
        print(f"Error: steps must be >= 2, got {args.steps}", file=sys.stderr)
        return 2

    target = start = None
    if args.pose is not None:
        try:
            target = parse_pose(args.pose)
        except ArmError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
    if args.move is not None:
        try:
            start = tuple(float(part) for part in
                          (args.move.split(",") if args.move else []))
        except ValueError:
            print(f"Error: --move must be 'q0,q1[,q2]', got {args.move!r}",
                  file=sys.stderr)
            return 2
        if args.to is None:
            print("Error: --move requires --to", file=sys.stderr)
            return 2

    if not args.quiet:
        print(BANNER)

    try:
        arm = load_arm(args.file or ARM_FILE)

        if args.mission is not None:
            mission = load_mission(args.mission, arm=arm)
            result = run_mission(arm, mission, dt=args.dt,
                                 speed_scale=args.speed_scale)
            if not args.quiet:
                print()
                print(render_report(result))
            payload = {
                "mission": result.mission,
                "total_time": round(result.total_time, 6),
                "move_time": round(result.move_time, 6),
                "samples": result.sample_count,
                "collisions": [hit.to_dict() for hit in result.collisions],
                "segments": [
                    {"name": segment.name,
                     "dwell": segment.dwell,
                     "trajectory": segment.trajectory.to_dict()}
                    for segment in result.segments],
            }
            code = 0 if not result.collisions else 3

        elif args.move is not None:
            goal_values = parse_pose(args.to or "")
            if args.cartesian:
                trajectory = plan_cartesian_move(
                    arm, start, goal_values, steps=args.steps,
                    dt=args.dt, speed_scale=args.speed_scale)
            else:
                if len(start) != arm.n_joints:
                    raise ArmError(
                        f"--move needs {arm.n_joints} joint value(s), "
                        f"got {len(start)}")
                if len(goal_values) != arm.n_joints:
                    raise ArmError(
                        f"--to needs {arm.n_joints} joint value(s), "
                        f"got {len(goal_values)}")
                trajectory = plan_joint_move(
                    arm, start, goal_values, dt=args.dt,
                    speed_scale=args.speed_scale)
            if not args.quiet:
                print()
                print(_render_trajectory(arm, trajectory,
                                         "cartesian" if args.cartesian
                                         else "joint"))
            collisions = check_collisions(arm, trajectory, ())
            payload = {"kind": "trajectory",
                       "trajectory": trajectory.to_dict(),
                       "collisions": [hit.to_dict() for hit in collisions]}
            code = 0

        else:
            q = solve_ik(arm, target)
            tool = pose(arm, q)
            if not args.quiet:
                print()
                print("IK SOLUTION - " + arm.name)
                print("-" * 68)
                for joint, value in zip(arm.joints, q):
                    print(f"  {joint.name:<10}: {value:+9.3f} deg")
                print(f"  tool pose : ({tool.x:+.4f}, {tool.y:+.4f}) "
                      f"yaw {tool.yaw:+.2f}")
                print(f"  target    : ({target[0]:+.4f}, {target[1]:+.4f})"
                      + (f" yaw {target[2]:+.2f}" if len(target) == 3 else ""))
            payload = {"kind": "ik", "arm": arm.name,
                       "q_deg": [round(value, 6) for value in q],
                       "pose": tool.to_dict()}
            code = 0

    except ArmError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
