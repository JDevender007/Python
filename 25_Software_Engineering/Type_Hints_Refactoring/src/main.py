"""Command line entry point for the Type Hints Refactoring project.

Usage
-----
    python src/main.py --demo                       # before/after comparison
    python src/main.py --file data/records.csv      # typed load + summary
    python src/main.py --spec data/interfaces.json  # manual contract check

Fully offline: sample CSVs and the interface spec ship in data/.
No network, no API keys, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import logging
import sys
from pathlib import Path

from typed import (
    ContractError,
    RecordError,
    contract_classes,
    load_interface_spec,
    load_records,
    run_demo,
    summarize,
    verify_contracts,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("refactor")

BANNER = """
========================================
 TYPE HINTS REFACTORING
   Before vs after, contracts checked
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Legacy vs typed module with manual interface contracts")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="before/after comparison with self-checks")
    action.add_argument("--file", type=Path, default=None,
                        help="sales CSV (id,units,price) to load + summarise")
    action.add_argument("--spec", type=Path, default=None,
                        help="interface spec JSON to verify against")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the banner")
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
                    return run_demo()
            return run_demo()
        except (RecordError, ContractError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.file is None and args.spec is None:
        parser.error("one of the arguments --demo --file --spec is required")

    if not args.quiet:
        print(BANNER)

    # Fast-fail: validate the flag inputs before any real work runs.
    if args.file is not None and not args.file.is_file():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 2
    if args.spec is not None and not args.spec.is_file():
        print(f"Error: file not found: {args.spec}", file=sys.stderr)
        return 2

    if args.file is not None:
        try:
            records = load_records(args.file)
            summary = summarize(records)
        except RecordError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(f"Records: {summary.count}")
        print(f"Total revenue: {summary.total}")
        print(f"Mean revenue: {summary.mean}")
        print(f"Top record: {summary.top_id}")
        print("\nDone.")
        return 0

    try:
        spec = load_interface_spec(args.spec)
    except ContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    results = verify_contracts(contract_classes(), spec)
    violations = sum(len(items) for items in results.values())
    if violations:
        for class_name, items in results.items():
            for item in items:
                print(f"Violation: {class_name}: {item}", file=sys.stderr)
        return 2
    print(f"OK: 0 violations across {len(results)} interfaces "
          f"({', '.join(results)})")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
