"""Command line entry point for the Home Automation Rules engine.

Usage
-----
    python src/main.py --demo                        # bundled rules + events
    python src/main.py --rules data/rules.json --events data/events.csv
    python src/main.py --rules r.json --events e.csv --out actuators.csv
    python src/main.py --demo --json run.json

Fully offline: local JSON rules and a sensor-event CSV in, an actuator
event log out. No hub, no network, no real devices.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from rules import (
    DEMO_EVENTS,
    DEMO_RULES,
    RuleEngine,
    RuleError,
    load_events,
    load_rules,
    log_actuator,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("rules")

BANNER = """
========================================
 HOME AUTOMATION RULES
   JSON rule set + event replay
   hysteresis, delays, actuator log
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
        description="Replay sensor events through an if-then rule engine")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="run the offline demo on the bundled files")
    mode.add_argument("--rules", type=Path, default=None,
                      help="JSON rules file (use with --events)")
    parser.add_argument("--events", type=Path, default=None,
                        help="sensor event CSV: timestamp,sensor,metric,value")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the actuator event log to this CSV")
    parser.add_argument("--json", type=Path, default=None,
                        help="write a run summary as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo, args.json)
        except RuleError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.rules is None:
        parser.error("one of the arguments --demo --rules is required")
    if args.events is None:
        print("Error: --events is required with --rules", file=sys.stderr)
        return 2

    try:
        rules = load_rules(args.rules)
        events = load_events(args.events)
        actuator_log = RuleEngine(rules).process(events)
    except RuleError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(f"Rules           : {len(rules)} from {args.rules.name}")
        print(f"Sensor events   : {len(events)} from {args.events.name}")
        print(f"Actuator events : {len(actuator_log)}")
        print()
        print(render_report(rules, actuator_log))

    if args.out is not None:
        try:
            written = log_actuator(actuator_log, args.out)
        except RuleError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"\nWrote {written}")

    if args.json is not None:
        triggers = (actuator_log[actuator_log["event"] == "trigger"]
                    .groupby("rule").size().to_dict())
        payload = {
            "mode": "replay",
            "rules": len(rules),
            "sensor_events": len(events),
            "actuator_events": len(actuator_log),
            "triggers": {key: int(value) for key, value in triggers.items()},
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
