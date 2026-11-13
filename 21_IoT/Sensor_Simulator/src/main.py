"""Command line entry point for the Sensor Simulator.

Usage
-----
    python src/main.py --demo                          # bundled fleet, full report
    python src/main.py --log readings.csv --ticks 96   # simulate your own log
    python src/main.py --log readings.csv --fault living_room_temp:spike:30:33
    python src/main.py --replay readings.csv           # summarise an existing log

Fully offline: local CSV in, CSV + summary out. No network, no real
devices, no API keys - the whole fleet is simulated in-process.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path

from sensors import (
    DEFAULT_INTERVAL_S,
    DEFAULT_SEED,
    DEFAULT_TICKS,
    SENSOR_KINDS,
    SensorError,
    default_fleet,
    load_log,
    log_readings,
    parse_fault,
    render_summary,
    run_demo,
    simulate,
    summarize,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("sensors")

BANNER = """
========================================
 SENSOR SIMULATOR
   Virtual sensors, offline CSV logging
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate virtual sensors (fully offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run the bundled offline demo")
    action.add_argument("--log", type=Path, default=None, metavar="CSV",
                        help="simulate the fleet and write a CSV log")
    action.add_argument("--replay", type=Path, default=None, metavar="CSV",
                        help="load an existing CSV log and print a summary")
    parser.add_argument("--sensor", choices=list(SENSOR_KINDS), default=None,
                        help="limit the fleet to one sensor kind")
    parser.add_argument("--ticks", type=int, default=DEFAULT_TICKS,
                        help=f"simulation ticks (default {DEFAULT_TICKS})")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S,
                        help=f"seconds between ticks "
                             f"(default {DEFAULT_INTERVAL_S:g})")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"RNG seed (default {DEFAULT_SEED})")
    parser.add_argument("--fault", action="append", default=[],
                        metavar="SENSOR:KIND:START:END",
                        help="inject a fault window, repeatable "
                             "(e.g. living_room_temp:spike:30:33)")
    parser.add_argument("--json", type=Path, default=None, metavar="PATH",
                        help="write the summary as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the banner")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # -- fast-fail: validate flag inputs BEFORE any simulation or IO ------ #
    if args.ticks < 1:
        parser.error(f"--ticks must be >= 1, got {args.ticks}")
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error(f"--interval must be > 0, got {args.interval}")
    try:
        faults = [parse_fault(text) for text in args.fault]
    except SensorError as exc:
        parser.error(str(exc))
    if faults and (args.demo or args.replay is not None):
        parser.error("--fault only applies to --log")

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            return run_demo(json_path=args.json)
        except SensorError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.log is None and args.replay is None:
        parser.error("one of the arguments --demo --log --replay is required")

    if not args.quiet:
        print(BANNER)
    try:
        if args.replay is not None:
            frame = load_log(args.replay)
            print(render_summary(frame))
            print(f"\nReplayed {len(frame)} readings from {args.replay.name}")
            payload = {"mode": "replay", "source": str(args.replay),
                       "readings": len(frame),
                       "summary": summarize(frame).to_dict("records")}
        else:
            specs = default_fleet(args.sensor)
            frame = simulate(specs, ticks=args.ticks, interval_s=args.interval,
                             seed=args.seed, faults=faults)
            log_readings(frame, args.log)
            print(render_summary(frame))
            print(f"\nWrote {len(frame)} readings to {args.log}")
            payload = {"mode": "log", "output": str(args.log),
                       "ticks": args.ticks, "readings": len(frame),
                       "summary": summarize(frame).to_dict("records")}
    except SensorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
