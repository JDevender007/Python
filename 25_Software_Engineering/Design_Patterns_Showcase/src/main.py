"""Command line entry point for the Design Patterns Showcase.

Usage
-----
    python src/main.py --demo                  # all 5 patterns, bundled data
    python src/main.py --list                  # list the pattern names
    python src/main.py --pattern strategy      # run one pattern section
    python src/main.py --file my_orders.json   # validate an orders JSON

Fully offline: order records ship in data/orders.json. No network,
no API keys, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import logging
import sys
from pathlib import Path

from patterns import (
    DEMO_ORDERS,
    PATTERN_NAMES,
    PatternError,
    load_orders,
    run_demo,
    run_pattern,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("patterns")

BANNER = """
========================================
 DESIGN PATTERNS SHOWCASE
   Five GoF patterns, fully offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Five GoF design patterns with runnable contracts")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run all five patterns with self-checks")
    action.add_argument("--list", action="store_true",
                        help="list the available pattern names")
    action.add_argument("--pattern", metavar="NAME", default=None,
                        help=f"run one pattern: {', '.join(PATTERN_NAMES)}")
    action.add_argument("--file", type=Path, default=None,
                        help="validate an orders JSON (list of records)")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the banner")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Fast-fail: validate flag inputs before any pattern work runs.
    if args.pattern is not None and \
            args.pattern.strip().lower() not in PATTERN_NAMES:
        print(f"Error: unknown pattern {args.pattern!r} "
              f"(expected one of {', '.join(PATTERN_NAMES)})",
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
        except PatternError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.list:
        for name in PATTERN_NAMES:
            print(name)
        return 0

    if args.pattern is None and args.file is None:
        parser.error(
            "one of the arguments --demo --list --pattern --file is required")

    if not args.quiet:
        print(BANNER)

    if args.file is not None:
        try:
            records = load_orders(args.file)
        except PatternError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        kinds = sorted({str(r["kind"]) for r in records})
        print(f"OK: {len(records)} valid order records "
              f"(kinds: {', '.join(kinds)})")
        return 0

    try:
        line = run_pattern(args.pattern or "")
    except PatternError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(line)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
