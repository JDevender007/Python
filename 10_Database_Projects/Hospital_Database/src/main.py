"""Command line front end for the hospital records lab.

Usage:
    python src/main.py --demo
    python src/main.py --demo --quiet
    python src/main.py --file data/patients.csv --json out.json
    python src/main.py --file data/patients.csv --audit
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hospital import (                                       # noqa: E402
    HospitalError,
    audit,
    format_cents,
    measure,
    render_groups,
    report,
    run_demo,
)


def _run_demo(quiet: bool, func, *args, **kwargs) -> int:
    """Run the offline demo; with --quiet no stream prints anything."""
    if not quiet:
        return func(*args, **kwargs)
    level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(level)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hospital-lab",
        description="Report blood groups and billing with NULL made explicit.",
    )
    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    parser.add_argument("--quiet", action="store_true", help="with --demo, print nothing")
    parser.add_argument(
        "--file",
        default=None,
        metavar="PATIENTS_CSV",
        help="patients CSV; the other three seed files are read from its folder",
    )
    parser.add_argument("--json", default=None, metavar="PATH", help="write a JSON report")
    parser.add_argument("--audit", action="store_true", help="re-run the checks; exit 1 on failure")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except HospitalError as exc:
            if not args.quiet:
                print(f"error: {exc}", file=sys.stderr)
            return 0
    try:
        measured = measure(args.file)
    except HospitalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    results = audit(measured)
    if args.audit:
        for name, ok in results:
            print(f"{'PASS' if ok else 'FAIL'}  {name}")
        failed = [name for name, ok in results if not ok]
        if failed:
            print(f"error: {len(failed)} check(s) failed", file=sys.stderr)
            return 1
        return 0

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report(measured), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if not args.quiet:
        print(render_groups(measured))
        print(
            f"billed {format_cents(measured['revenue']['billed'])}, "
            f"average {format_cents(measured['revenue']['average'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
