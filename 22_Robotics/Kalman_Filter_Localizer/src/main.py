"""Command line entry point for the Kalman Filter Localizer project.

Usage
-----
    python src/main.py --demo
    python src/main.py
    python src/main.py --scenario data/scenario.json --gate 9.21
    python src/main.py --json run.json --quiet

Fully offline: the landmarks are a local CSV and the scenario a local JSON
file. No network, no API keys, no ROS, no hardware.
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

from localizer import (
    LANDMARK_FILE,
    SCENARIO_FILE,
    USE_SCENARIO_GATE,
    LocalizerError,
    load_landmarks,
    load_scenario,
    mean_nees,
    render_map,
    render_report,
    rmse_position,
    run_demo,
    run_ekf,
    simulate,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("localizer")

BANNER = """
========================================
 KALMAN FILTER LOCALIZER
   EKF + odometry + landmark sightings
   offline, deterministic
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
        description="Localise a differential-drive robot offline")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled localisation demo with "
                             "self-checks")
    parser.add_argument("--scenario", type=Path, default=None,
                        help="scenario JSON file (default: bundled sample)")
    parser.add_argument("--landmarks", type=Path, default=None,
                        help="landmark CSV file (default: bundled sample)")
    parser.add_argument("--gate", type=float, default=None,
                        help="chi-square innovation gate (default: from the "
                             "scenario)")
    parser.add_argument("--no-gate", action="store_true",
                        help="accept every measurement, ignoring the gate")
    parser.add_argument("--map", action="store_true",
                        help="also print the ASCII map")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the run summary as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def _payload(scenario, simulation, estimates, odometry_rmse: float,
             ekf_rmse: float) -> dict:
    rejected = sorted(estimate.step for estimate in estimates
                      if estimate.accepted is False)
    return {
        "scenario": scenario.name,
        "seed": scenario.seed,
        "steps": simulation.steps,
        "measurements": len(simulation.measurements),
        "updates": sum(1 for estimate in estimates if estimate.accepted),
        "rejected_steps": rejected,
        "outlier_steps": sorted(simulation.outlier_steps),
        "gate": scenario.gate,
        "odometry_rmse": round(odometry_rmse, 6),
        "ekf_rmse": round(ekf_rmse, 6),
        "mean_nees": round(mean_nees(estimates, simulation.truth), 6),
        "final_sigma_xy": round(estimates[-1].sigma_xy, 6),
        "estimates": [estimate.to_dict() for estimate in estimates],
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if args.gate is not None or args.no_gate:
            parser.error("--demo does not accept --gate or --no-gate")
        if not args.quiet:
            print(BANNER)
        try:
            return _run_demo(args.quiet, run_demo)
        except LocalizerError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0

    # fast-fail: flags are validated before any file is read
    if args.gate is not None and args.no_gate:
        parser.error("--gate and --no-gate are mutually exclusive")
    if args.gate is not None:
        if not math.isfinite(args.gate) or args.gate <= 0:
            print(f"Error: gate must be > 0, got {args.gate}",
                  file=sys.stderr)
            return 2

    if not args.quiet:
        print(BANNER)

    try:
        scenario = load_scenario(args.scenario or SCENARIO_FILE)
        landmarks = load_landmarks(args.landmarks or LANDMARK_FILE)
        simulation = simulate(scenario, landmarks)

        gate = None if args.no_gate else (
            args.gate if args.gate is not None else USE_SCENARIO_GATE)
        estimates = run_ekf(scenario, simulation, landmarks, gate=gate)

    except LocalizerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    ekf_poses = tuple(estimate.pose for estimate in estimates)
    truth = simulation.truth
    odometry_rmse = rmse_position(simulation.odometry[1:], truth[1:])
    ekf_rmse = rmse_position(ekf_poses, truth[1:])

    if not args.quiet:
        print()
        print(render_report(simulation, estimates, odometry_rmse, ekf_rmse))
        if args.map:
            print()
            print(render_map(landmarks, simulation, estimates))
            print("\nMap legend: # truth, . odometry, e estimate, L landmark")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = _payload(scenario, simulation, estimates, odometry_rmse,
                           ekf_rmse)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
