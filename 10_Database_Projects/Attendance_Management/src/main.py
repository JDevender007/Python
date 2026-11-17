"""Command line front end for the attendance lab.

Usage:
    python src/main.py --demo
    python src/main.py --demo --quiet
    python src/main.py --file data/attendance_log.csv --json out.json
    python src/main.py --from 2024-03-04 --to 2024-03-31
    python src/main.py --audit
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

from attendance import (                                     # noqa: E402
    GRACE,
    DomainError,
    audit,
    build_database,
    late_report,
    legacy_logs_between,
    logs_between,
    measure,
    problems,
    read_log,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="attendance-lab",
        description="Read check-in timestamps as dates and integer minutes.")
    parser.add_argument("--file", default=None, metavar="PATH",
                        help="a check-in CSV (default: the bundled one)")
    parser.add_argument("--from", dest="start", default="2024-03-01",
                        metavar="YYYY-MM-DD", help="the first day of the range")
    parser.add_argument("--to", dest="end", default="2024-03-31",
                        metavar="YYYY-MM-DD", help="the last day of the range")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the report and the measurements to PATH")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def _run_demo(quiet: bool, func, *args, **kwargs) -> int:
    """Run the offline demo; with --quiet no stream prints anything."""
    if not quiet:
        return func(*args, **kwargs)
    level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(level)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except DomainError as error:
            if not args.quiet:
                print(f"error: {error}", file=sys.stderr)
            return 0

    try:
        people, logs = read_log(args.file)
        conn = build_database(people, logs)
    except DomainError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        report = late_report(conn, args.start, args.end)
        rows = logs_between(conn, args.start, args.end)
        legacy_rows = legacy_logs_between(conn, args.start, args.end)
    except DomainError as error:
        conn.close()
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {len(rows)} check-ins from {args.start} to {args.end}, "
              f"grace {GRACE}")
        print(f"  {'code':<8}{'name':<17}{'days':>5}{'late':>6}"
              f"{'minutes':>9}{'mean':>6}")
        for row in report:
            print(f"  {row['code']:<8}{row['full_name']:<17}{row['days']:>5}"
                  f"{row['late_days']:>6}{row['late_minutes']:>9}"
                  f"{row['average']:>6}")
        print(f"  the legacy BETWEEN reads {len(legacy_rows)} of "
              f"{len(rows)} rows")

    checks = []
    measured: dict = {}
    if args.audit:
        measured = measure(conn)
        checks = audit(measured, make_database=build_database)
        if not args.quiet:
            print()
            for name, okay in checks:
                print(f"  {'PASS' if okay else 'FAIL'}  {name}")

    failed = problems(checks)
    if failed and not args.quiet:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "from": args.start,
            "to": args.end,
            "check_ins": len(rows),
            "legacy_check_ins": len(legacy_rows),
            "report": report,
            "measurements": measured,
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the report to {destination}")

    conn.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
