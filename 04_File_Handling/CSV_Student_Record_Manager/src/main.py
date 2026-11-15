"""Command line interface for the student table.

    python src/main.py --demo
    python src/main.py                          # every row
    python src/main.py --search priya
    python src/main.py --student 421123102003
    python src/main.py --sort marks
    python src/main.py --average
    python src/main.py --report
    python src/main.py --add 421123102009:Nadia Iqbal:CSE:1:90.5
    python src/main.py --update 421123102001:marks=91.25
    python src/main.py --remove 421123102008
    python src/main.py --audit
    python src/main.py --legacy
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from records import (
    DATA_FILE,
    DEPARTMENTS,
    HEADER,
    LEGACY_AVERAGE,
    LEGACY_DUPLICATE,
    LEGACY_FLOAT_ROW,
    LEGACY_SAVE,
    MAX_MARKS,
    Student,
    StudentTable,
    RecordError,
    format_marks,
    load_table,
    parse_marks,
    parse_whole,
    run_demo,
)

BANNER = """
========================================
 STUDENT RECORDS
   a CSV file, and exact marks
========================================
"""


def _split(spec: str, parts: int, shape: str) -> list[str]:
    pieces = [piece.strip() for piece in spec.split(":")]
    if len(pieces) != parts or not all(pieces):
        raise RecordError(f"expected {shape}, got {spec!r}")
    return pieces


def _rows(table: StudentTable) -> list:
    return [student.to_dict() for student in table]


def _print_rows(rows) -> None:
    print(f"  {HEADER[0]:<13} {HEADER[1]:<16} {HEADER[2]:<4} {HEADER[3]:<4} "
          f"{HEADER[4]:>6}")
    for row in rows:
        print(f"  {row['roll']:<13} {row['name']:<16.16} "
              f"{row['department']:<4} {row['year']:<4} "
              f"{row['marks']:>6}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A student table read and written as strict CSV.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="the CSV file (default: data/students.csv)")
    parser.add_argument("--list", action="store_true",
                        help="every row (the default)")
    parser.add_argument("--search", metavar="TEXT",
                        help="rows whose roll, name or department matches")
    parser.add_argument("--student", metavar="ROLL",
                        help="one row by roll number")
    parser.add_argument("--sort", choices=("roll", "name", "marks"),
                        help="order the rows")
    parser.add_argument("--average", action="store_true",
                        help="the mean of every mark")
    parser.add_argument("--report", action="store_true",
                        help="counts and means by department")
    parser.add_argument("--add", metavar="ROLL:NAME:DEPT:YEAR:MARKS",
                        help="append a row")
    parser.add_argument("--update", metavar="ROLL:FIELD=VALUE",
                        help="replace fields of a row (name, department, "
                             "year or marks)")
    parser.add_argument("--remove", metavar="ROLL", help="delete a row")
    parser.add_argument("--audit", action="store_true",
                        help="run the five invariants")
    parser.add_argument("--legacy", action="store_true",
                        help="show the legacy defects the demo proves")
    parser.add_argument("--write", type=Path, metavar="PATH",
                        help="save the table after the change")
    parser.add_argument("--json", type=Path, metavar="PATH",
                        help="write the result as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="write no standard output")
    args = parser.parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo()
        else:
            run_demo()
        return 0

    try:
        if args.legacy:
            table = load_table(args.file)
            payload = {"mode": "legacy", "marks_type": LEGACY_FLOAT_ROW,
                       "save": LEGACY_SAVE, "duplicate": LEGACY_DUPLICATE,
                       "average": LEGACY_AVERAGE,
                       "padded_roll_is_duplicate":
                           " 421123102001" in table,
                       "legacy_thinks_padded_roll_is_duplicate": False,
                       "report_lines": len(table) + 1}
            if not args.quiet:
                print(BANNER)
                print(f"  marks      {LEGACY_FLOAT_ROW}   (a type the domain "
                      f"does not have)")
                print(f"  save       {LEGACY_SAVE}   (truncates before it "
                      f"writes)")
                print(f"  duplicate  {LEGACY_DUPLICATE}")
                print(f"  average    {LEGACY_AVERAGE}")
                print(f"\n  ' 421123102001' is {table.student('421123102001').roll} "
                      f"here and a second student to the legacy test")
                print(f"  the legacy report has {len(table) + 1} lines: the "
                      f"same rows as the data file")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        table = load_table(args.file)
        payload: dict = {"mode": "table", "rows": len(table),
                         "average": format_marks(table.average_marks()),
                         "file": args.file.name}

        if args.search is not None:
            found = table.search(args.search)
            payload = {"mode": "search", "needle": args.search,
                       "count": len(found),
                       "rows": [student.to_dict() for student in found]}
            if not args.quiet:
                print(BANNER)
                _print_rows(payload["rows"])
                print(f"\n  {len(found)} row(s) match {args.search!r}")
        elif args.student is not None:
            student = table.student(args.student)
            payload = {"mode": "student", "student": student.to_dict()}
            if not args.quiet:
                print(BANNER)
                _print_rows([student.to_dict()])
        elif args.sort is not None:
            key = {"roll": lambda s: s.roll,
                   "name": lambda s: (s.name.casefold(), s.roll),
                   "marks": lambda s: (-s.marks, s.roll)}[args.sort]
            ordered = sorted(table, key=key)
            payload = {"mode": "sort", "by": args.sort,
                       "rows": [student.to_dict() for student in ordered]}
            if not args.quiet:
                print(BANNER)
                _print_rows(payload["rows"])
        elif args.average:
            payload = {"mode": "average", "rows": len(table),
                       "average": format_marks(table.average_marks()),
                       "total": format_marks(table.total_marks)}
            if not args.quiet:
                print(BANNER)
                print(f"  {len(table)} rows, {payload['total']} marks in "
                      f"total")
                print(f"  average {payload['average']} (rounded half up from "
                      f"{table.total_marks}/{len(table)})")
        elif args.report:
            rows = table.report()
            payload = {"mode": "report", "departments": rows,
                       "average": format_marks(table.average_marks()),
                       "top": table.top(1)[0].to_dict() if len(table) else None}
            if not args.quiet:
                print(BANNER)
                for row in rows:
                    print(f"  {row['department']:<5} {row['students']:>2} "
                          f"student(s)  average {row['average']:>6}  best "
                          f"{row['best']} at {row['best_marks']}")
                print(f"\n  {len(table)} rows, average "
                      f"{payload['average']}")
        elif args.add is not None:
            roll, name, department, year, marks = _split(
                args.add, 5, "ROLL:NAME:DEPARTMENT:YEAR:MARKS")
            student = table.add(Student(roll, name, department,
                                        parse_whole(year, "year"),
                                        parse_marks(marks)))
            payload = {"mode": "add", "student": student.to_dict(),
                       "rows": len(table)}
            if not args.quiet:
                print(BANNER)
                print(f"  added {student.roll}  {student.name}  "
                      f"{student.department} year {student.year}  "
                      f"{student.marks_text}")
                print(f"  the table now holds {len(table)} rows")
        elif args.update is not None:
            roll, change = _split(args.update, 2, "ROLL:FIELD=VALUE")
            if "=" not in change:
                raise RecordError(f"expected FIELD=VALUE, got {change!r}")
            field, value = (piece.strip() for piece in change.split("=", 1))
            if field == "marks":
                value = parse_marks(value)
            elif field == "year":
                value = parse_whole(value, "year")
            student = table.update(roll, **{field: value})
            payload = {"mode": "update", "student": student.to_dict()}
            if not args.quiet:
                print(BANNER)
                print(f"  {student.roll}: {field} is now "
                      f"{value if field != 'marks' else student.marks_text}")
        elif args.remove is not None:
            student = table.remove(args.remove)
            payload = {"mode": "remove", "student": student.to_dict(),
                       "rows": len(table)}
            if not args.quiet:
                print(BANNER)
                print(f"  removed {student.roll}  {student.name}")
                print(f"  the table now holds {len(table)} rows")
        elif args.audit:
            checks = table.audit()
            payload = {"mode": "audit",
                       "checks": [{"name": name, "passed": passed}
                                  for name, passed in checks],
                       "clean": all(passed for _, passed in checks)}
            if not args.quiet:
                print(BANNER)
                for name, passed in checks:
                    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
                print(f"\n  {sum(1 for _, ok in checks if ok)}/{len(checks)} "
                      f"checks passed")
        else:
            payload = {"mode": "list", "rows": _rows(table),
                       "count": len(table),
                       "average": format_marks(table.average_marks())}
            if not args.quiet:
                print(BANNER)
                _print_rows(payload["rows"])
                print(f"\n  {len(table)} rows, average "
                      f"{payload['average']}")

        if args.write:
            table.save(args.write)
            payload["written"] = args.write.name
            if not args.quiet:
                print(f"  written to {payload['written']}")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except RecordError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
