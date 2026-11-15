"""Command line front end for the report lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reportlab import (                                      # noqa: E402
    GAP_LIMIT,
    ReportError,
    audit,
    build_report,
    money,
    problems,
    read_table,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="report-lab",
        description="Profile a CSV column by column, print every mean with the "
                    "number of values behind it, and keep money in whole cents.")
    parser.add_argument("--data", default=None,
                        help="a CSV file (default: the bundled one)")
    parser.add_argument("--group", default="region", metavar="COLUMN",
                        help="the column to total revenue by (default: region)")
    parser.add_argument("--csv", default=None, metavar="PATH",
                        help="write the column report to PATH as CSV")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the whole report to PATH as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        table = read_table(args.data) if args.data else read_table()
        report = build_report(table, args.group)
    except ReportError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {report.rows} rows, {len(table.header)} columns, grouped by "
              f"{report.key}")
        for line in report.table_lines():
            print(line)
        print(f"  {GAP_LIMIT}% is the gap limit; flagged: "
              f"{', '.join(report.flagged()) or 'none'}")

        print("  revenue, in whole cents:")
        for group in report.groups:
            print(f"    {group.line()}")
        print(f"    {'total':<10}{'':>14} {report.units():>4} unit(s) "
              f"revenue {money(report.revenue())}")

        for entry in report.excluded:
            print(f"  excluded line {entry.line} {entry.order}: {entry.reason}")
        print(f"  {sum(group.orders for group in report.groups)} grouped + "
              f"{len(report.excluded)} excluded = {report.rows} rows")

    if args.csv:
        target = Path(args.csv)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(report.csv_lines()) + "\n",
                          encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {len(report.columns)} column(s) to {target}")

    failed_checks = []
    if args.audit:
        print()
        checks = audit(report)
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rows": report.rows,
            "key": report.key,
            "gap_limit": GAP_LIMIT,
            "columns": [{"name": column.name, "kind": column.kind,
                         "present": column.present, "missing": column.missing,
                         "total": column.total,
                         "mean": column.mean(),
                         "flagged": column.gap()}
                        for column in report.columns],
            "groups": [{"name": group.name, "orders": group.orders,
                        "units": group.units, "revenue": group.revenue,
                        "revenue_text": money(group.revenue)}
                       for group in report.groups],
            "excluded": [{"line": entry.line, "order": entry.order,
                          "reason": entry.reason}
                         for entry in report.excluded],
            "revenue_cents": report.revenue(),
            "accounts": report.accounts(),
        }
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the report to {target}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
