"""Command line entry point for the Pythonic Toolkit.

Usage
-----
    python src/main.py --demo                       # all idiom recipes
    python src/main.py --file data/records.json     # validate records
    python src/main.py --run generators             # run one recipe
    python src/main.py --list                       # list the recipes

Fully offline: records ship in data/records.json, stdlib only.
No network, no API keys, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import logging
import sys
from pathlib import Path

from toolkit import (
    RECIPE_NAMES,
    ToolkitError,
    load_records,
    record_summary,
    run_demo,
    run_recipe,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("toolkit")

BANNER = """
========================================
 PYTHONIC TOOLKIT
   Idiomatic Python, stdlib only
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decorators, context managers, generators, class idioms")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run every recipe with self-checks")
    action.add_argument("--file", type=Path, default=None,
                        help="validate a records JSON against RECORD_SPEC")
    action.add_argument("--run", metavar="RECIPE", default=None,
                        help=f"run one recipe: {', '.join(RECIPE_NAMES)}")
    action.add_argument("--list", action="store_true",
                        help="list the available recipe names")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the banner")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Fast-fail: validate the flag input before any recipe work runs.
    if args.run is not None and \
            args.run.strip().lower() not in RECIPE_NAMES:
        print(f"Error: unknown recipe {args.run!r} "
              f"(expected one of {', '.join(RECIPE_NAMES)})",
              file=sys.stderr)
        return 2

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    return run_demo()
            return run_demo()
        except ToolkitError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.list:
        for name in RECIPE_NAMES:
            print(name)
        return 0

    if args.file is None and args.run is None:
        parser.error(
            "one of the arguments --demo --file --run --list is required")

    if not args.quiet:
        print(BANNER)

    if args.file is not None:
        try:
            records = load_records(args.file)
        except ToolkitError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        summary = record_summary(records)
        print(f"OK: {int(summary['count'])} valid records; "
              f"mean age {summary['mean_age']}, "
              f"mean score {summary['mean_score']}")
        return 0

    try:
        line = run_recipe(args.run or "")
    except ToolkitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(line)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
