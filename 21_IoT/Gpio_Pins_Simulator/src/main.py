"""Command line entry point for the GPIO Pins Simulator.

Usage
-----
    python src/main.py --demo
    python src/main.py --scenario data/scenario.json
    python src/main.py --scenario data/scenario.json --json run.json
    python src/main.py --scenario data/scenario.json --quiet

Fully offline: a local JSON scenario in, a transcript plus a board
snapshot out. No hardware, no kernel driver, no network.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from gpio import (
    DEFAULT_DEBOUNCE,
    EDGES,
    MAX_PIN,
    MIN_PIN,
    MODES,
    PULLS,
    GpioError,
    load_scenario,
    render_report,
    run_demo,
    run_scenario,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("gpio")

BANNER = """
========================================
 GPIO PINS SIMULATOR
   modes, pulls, edges, PWM, debounce
   no hardware, no network
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
        description="Replay a JSON scenario against a simulated GPIO board")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="run the offline demo")
    mode.add_argument("--scenario", type=Path, default=None,
                      help="JSON scenario with 'pins' and 'steps'")
    parser.add_argument("--debounce", type=int, default=DEFAULT_DEBOUNCE,
                        help=f"min_stable samples for debounced inputs "
                             f"(default {DEFAULT_DEBOUNCE})")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the transcript and snapshot as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except GpioError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.scenario is None:
        parser.error("one of the arguments --demo --scenario is required")

    # fast-fail: validate flags before reading the scenario
    if args.debounce < 1:
        print(f"Error: debounce must be >= 1, got {args.debounce}",
              file=sys.stderr)
        return 2

    try:
        scenario = load_scenario(args.scenario)
        result = run_scenario(scenario)
    except GpioError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    board = result["board"]
    if args.debounce != DEFAULT_DEBOUNCE:
        for pin in board.pins:
            if pin.mode == "input":
                try:
                    board.attach_debouncer(pin.number, args.debounce)
                except GpioError as exc:
                    print(f"Error: {exc}", file=sys.stderr)
                    return 2

    if not args.quiet:
        print(BANNER)
        print(f"Scenario        : {scenario['name']}")
        print(f"Pins            : {len(scenario['pins'])}    "
              f"Steps: {len(scenario['steps'])}")
        print("\nTranscript:")
        for index, line in enumerate(result["transcript"], start=1):
            print(f"  {index:>2}. {line}")
        print()
        print(render_report(board))

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "scenario": scenario["name"],
            "transcript": result["transcript"],
            "snapshot": result["snapshot"],
            "events": board.to_dict(keep_events=True)["events"],
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
