"""Command line entry point for the Census Data Analyzer.

Usage
-----
    python src/main.py --demo                       # bundled sample data
    python src/main.py --file census.csv            # your own data
    python src/main.py --file census.csv --top 10
    python src/main.py --file census.csv --json report.json

Fully offline: reads a local CSV and writes local files only.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from census_analyzer import (
    CensusError,
    analyze,
    load_census,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("census")

BANNER = """
========================================
 CENSUS DATA ANALYZER
   local demographic analysis, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyse a local census CSV (offline)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run the offline demo")
    source.add_argument("--file", type=Path, default=None, help="census CSV to analyse")
    parser.add_argument("--top", type=int, default=5,
                        help="ranking size for income/poverty lists (default 5)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the report as JSON to this path")
    parser.add_argument("--quiet", action="store_true", help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if args.top < 1:
        print("Error: --top must be >= 1", file=sys.stderr)
        return 2

    print(BANNER)
    try:
        frame = load_census(args.file)
        report = analyze(frame, top=args.top)
    except CensusError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(report))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
