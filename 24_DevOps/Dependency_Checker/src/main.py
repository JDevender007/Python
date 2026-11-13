"""Command line entry point for the Dependency Checker.

Usage
-----
    python src/main.py --demo                              # bundled lists
    python src/main.py --file requirements.txt             # check your list
    python src/main.py --file pyproject.toml               # pyproject deps
    python src/main.py --file requirements.txt --json out.json

Fully offline: requirement lists in, severity report out, installed
versions read from local package metadata (importlib.metadata).
No pip, no index queries, no downloads, no network.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from depcheck import (
    DepError,
    check_requirements,
    parse_any,
    render_report,
    run_demo,
    severity_counts,
    status_counts,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("depcheck")

BANNER = """
========================================
 DEPENDENCY CHECKER
   offline version + severity report
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare requirement lists against locally installed "
                    "versions (offline, no pip/index)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="check the bundled requirements + pyproject")
    action.add_argument("--file", type=Path, default=None,
                        help="requirements.txt or pyproject.toml to check")
    parser.add_argument("--json", type=Path, default=None,
                        help="write results as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


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
        except DepError as exc:
            # --demo never fails on user input: bundled data ships with the
            # repo, so a DepError here is reported but not fatal.
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    if args.file is None:
        parser.error("one of the arguments --demo --file is required")

    if not args.quiet:
        print(BANNER)
    try:
        # parse first so bad input fails fast, before any metadata lookups
        requirements = parse_any(args.file)
        results = check_requirements(requirements)
    except DepError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(results, f"DEPENDENCY CHECK - {args.file.name}"))
        print("\nDone.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source": str(args.file),
            "results": [r.to_dict() for r in results],
            "status_counts": status_counts(results),
            "severity_counts": severity_counts(results),
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
