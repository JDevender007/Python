"""Command line entry point for the Survey Data Analyzer.

Usage
-----
    python src/main.py --demo                       # bundled sample survey
    python src/main.py --file survey.csv            # your own data
    python src/main.py --file survey.csv --group gender
    python src/main.py --file survey.csv --json report.json
    python src/main.py --file survey.csv --quiet

Fully offline: reads a local CSV and writes local files only.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from survey_analyzer import (
    GROUP_COLUMNS,
    SurveyError,
    analyze,
    load_survey,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("survey")

BANNER = """
========================================
 SURVEY DATA ANALYZER
   local CSV analysis, no network
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyse a local survey CSV (offline)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run the offline demo")
    source.add_argument("--file", type=Path, default=None, help="survey CSV to analyse")
    parser.add_argument("--group", default="department", choices=GROUP_COLUMNS,
                        help="grouping for comparisons and crosstab (default department)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the report as JSON to this path")
    parser.add_argument("--quiet", action="store_true", help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    print(BANNER)
    try:
        frame = load_survey(args.file)
        report = analyze(frame, group=args.group)
    except SurveyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(report, group=args.group))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2),
                             encoding="utf-8")
        print(f"\nWrote {args.json}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
