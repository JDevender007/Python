"""Command line interface for the student registry.

    python src/main.py --demo
    python src/main.py                                  # every student
    python src/main.py --search khan
    python src/main.py --student CS-2023-014
    python src/main.py --top 3
    python src/main.py --department "Computer Science"
    python src/main.py --report
    python src/main.py --add CS-2024-090:Nadia Iqbal:Computer Science:1:nadia.iqbal@example.edu:9000000000
    python src/main.py --course CS-2023-014:CS304:Compilers:4:A
    python src/main.py --retake CS-2023-007:CS301:B
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

from students import (
    DATA_FILE,
    DEPARTMENTS,
    LEGACY_CGPA,
    LEGACY_IMPORT,
    LEGACY_SEARCH,
    LEGACY_SORT,
    LEGACY_VALIDATOR,
    Course,
    Registry,
    Student,
    StudentError,
    Transcript,
    check_year,
    format_points,
    legacy_rows,
    legacy_top,
    load_registry,
    normalise_department,
    run_demo,
    save_registry,
)

BANNER = """
========================================
 STUDENT REGISTRY
   a CGPA computed from a transcript
========================================
"""


def _split(spec: str, parts: int, shape: str) -> list[str]:
    pieces = [piece.strip() for piece in spec.split(":")]
    if len(pieces) != parts or not all(pieces):
        raise StudentError(f"expected {shape}, got {spec!r}")
    return pieces


def _count(text: str, label: str = "a whole number") -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        raise StudentError(f"{text!r} is not {label}") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A registry whose CGPAs are computed from transcripts.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="student file (default: data/students.json)")
    parser.add_argument("--students", action="store_true",
                        help="one line per student (the default)")
    parser.add_argument("--search", metavar="TEXT",
                        help="students whose roll, name, department or email "
                             "matches")
    parser.add_argument("--student", metavar="ROLL",
                        help="one student and their transcript")
    parser.add_argument("--top", metavar="N", default=None,
                        help="the best N CGPAs (default 3)")
    parser.add_argument("--department", metavar="NAME",
                        help="students in one department")
    parser.add_argument("--report", action="store_true",
                        help="students and credits by department")
    parser.add_argument("--add", metavar="ROLL:NAME:DEPT:YEAR:EMAIL:PHONE",
                        help="register a new student")
    parser.add_argument("--course", metavar="ROLL:CODE:TITLE:CREDITS:GRADE",
                        help="record a course (a retake replaces the grade)")
    parser.add_argument("--retake", metavar="ROLL:CODE:GRADE",
                        help="replace the grade of a course already recorded")
    parser.add_argument("--audit", action="store_true",
                        help="run the five invariants")
    parser.add_argument("--legacy", action="store_true",
                        help="show the legacy defects the demo proves")
    parser.add_argument("--write", type=Path, metavar="PATH",
                        help="save the registry after the change")
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
            registry = load_registry(args.file)
            claimed = legacy_top(legacy_rows(registry))
            best = registry.top(1)[0]
            payload = {
                "mode": "legacy",
                "cgpa": LEGACY_CGPA,
                "search": LEGACY_SEARCH,
                "sort": LEGACY_SORT,
                "validator": LEGACY_VALIDATOR,
                "import": LEGACY_IMPORT,
                "claimed_top": claimed["roll"],
                "claimed_cgpa": claimed["cgpa"],
                "computed_top": best.roll,
                "computed_cgpa": best.cgpa,
            }
            if not args.quiet:
                print(BANNER)
                print(f"  cgpa       {LEGACY_CGPA}   (a typed number)")
                print(f"  search     {LEGACY_SEARCH}   (one row, not a search)")
                print(f"  sort       {LEGACY_SORT}")
                print(f"  validator  {LEGACY_VALIDATOR}   (a namespace, not a "
                      f"type)")
                print(f"  import     {LEGACY_IMPORT}")
                print(f"\n  the column ranks {claimed['roll']} first on a "
                      f"typed {claimed['cgpa']:.2f}")
                print(f"  the transcripts rank {best.roll} first on a "
                      f"computed {best.cgpa}")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        registry = load_registry(args.file)
        payload: dict = {"mode": "students", "registry": registry.name,
                         "scale": registry.scale.name,
                         "students": len(registry),
                         "credits": registry.total_credits}

        if args.search is not None:
            found = registry.search(args.search)
            payload = {"mode": "search", "needle": args.search,
                       "count": len(found),
                       "found": [student.roll for student in found]}
            if not args.quiet:
                print(BANNER)
                for student in found:
                    print(f"  {student}")
                print(f"\n  {len(found)} student(s) match {args.search!r}")
        elif args.student is not None:
            student = registry.student(args.student)
            payload = {"mode": "student", "roll": student.roll,
                       "name": student.name,
                       "department": student.department,
                       "year": student.year, "email": student.email,
                       "phone": student.phone, "credits": student.credits,
                       "cgpa": student.cgpa_text,
                       "courses": [course.to_dict()
                                   for course in student.courses]}
            if not args.quiet:
                print(BANNER)
                print(f"  {student.roll}  {student.name}  "
                      f"{student.department}  year {student.year}")
                print(f"  {student.email}  {student.phone}")
                print(f"  {len(student.courses)} course(s), "
                      f"{student.credits} credits, CGPA {student.cgpa_text}")
                for course in student.courses:
                    print(f"  {course}")
        elif args.department is not None:
            name = normalise_department(args.department)
            members = registry.by_department().get(name, ())
            payload = {"mode": "department", "department": name,
                       "count": len(members),
                       "students": [student.roll for student in members]}
            if not args.quiet:
                print(BANNER)
                for student in members:
                    print(f"  {student}")
                print(f"\n  {len(members)} student(s) in {name}")
        elif args.report:
            grouped = registry.by_department()
            rows = [{"department": department, "students": len(students),
                     "credits": sum(student.credits for student in students)}
                    for department, students in grouped.items()]
            payload = {"mode": "report", "departments": rows,
                       "mean_credits": registry.mean_credits()}
            if not args.quiet:
                print(BANNER)
                for row in rows:
                    print(f"  {row['department']:<18} {row['students']:>2} "
                          f"student(s) {row['credits']:>4} credits")
                print(f"\n  mean {registry.mean_credits()} credits per "
                      f"student")
        elif args.add is not None:
            roll, name, department, year, email, phone = _split(
                args.add, 6, "ROLL:NAME:DEPARTMENT:YEAR:EMAIL:PHONE")
            student = Student(roll, name, department, check_year(_count(year)),
                              email, phone, Transcript(registry.scale))
            registry.add(student)
            payload = {"mode": "add", "roll": student.roll,
                       "name": student.name,
                       "department": student.department,
                       "year": student.year}
            if not args.quiet:
                print(BANNER)
                print(f"  added {student.roll}  {student.name}  "
                      f"{student.department} year {student.year}")
                print(f"  no CGPA yet: a new student has no courses")
        elif args.course is not None:
            roll, code, title, credits, grade = _split(
                args.course, 5, "ROLL:CODE:TITLE:CREDITS:GRADE")
            student = registry.student(roll)
            existed = code.strip().upper() in student.transcript
            course = student.add_course(
                Course(code, title, _count(credits, "a whole number"), grade))
            payload = {"mode": "course", "roll": student.roll,
                       "code": course.code, "credits": course.credits,
                       "grade": course.grade, "replaced": existed,
                       "cgpa": student.cgpa}
            if not args.quiet:
                print(BANNER)
                verb = "replaced" if existed else "recorded"
                print(f"  {verb} {course.code} for {student.roll}: "
                      f"{course.credits} credits at {course.grade}")
                print(f"  CGPA {student.cgpa} over {student.credits} "
                      f"credits")
        elif args.retake is not None:
            roll, code, grade = _split(args.retake, 3, "ROLL:CODE:GRADE")
            student = registry.student(roll)
            before = student.transcript[code].grade
            course = student.retake(code, grade)
            payload = {"mode": "retake", "roll": student.roll,
                       "code": course.code, "was": before,
                       "now": course.grade, "credits": student.credits,
                       "cgpa": student.cgpa}
            if not args.quiet:
                print(BANNER)
                print(f"  {course.code} on {student.roll}: {before} -> "
                      f"{course.grade}")
                print(f"  {student.credits} credits, CGPA {student.cgpa} "
                      f"(the attempt was replaced, not added)")
        elif args.audit:
            checks = registry.audit()
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
        elif args.top is not None:
            count = _count(args.top or "3", "a whole number")
            ranked = registry.top(count)
            payload = {"mode": "top", "count": len(ranked),
                       "ranked": [{"rank": place, "roll": student.roll,
                                   "name": student.name,
                                   "cgpa": student.cgpa,
                                   "credits": student.credits}
                                  for place, student in enumerate(ranked, 1)]}
            if not args.quiet:
                print(BANNER)
                for place, student in enumerate(ranked, 1):
                    print(f"  {place}. {student.roll:<13} "
                          f"{student.name:<18.18} {student.department:<18.18} "
                          f"{student.cgpa:>5}")
                print(f"\n  ranked by the exact credit-weighted score, ties by "
                      f"roll number")
        else:
            payload = {"mode": "students", "registry": registry.name,
                       "scale": registry.scale.name,
                       "count": len(registry),
                       "credits": registry.total_credits,
                       "mean_credits": registry.mean_credits(),
                       "students": [{"roll": student.roll,
                                     "name": student.name,
                                     "department": student.department,
                                     "year": student.year,
                                     "credits": student.credits,
                                     "cgpa": student.cgpa_text}
                                    for student in registry]}
            if not args.quiet:
                print(BANNER)
                for student in registry:
                    print(f"  {student}")
                print(f"\n  {len(registry)} students, "
                      f"{registry.total_credits} credits, mean "
                      f"{registry.mean_credits()} credits")

        if args.write:
            save_registry(args.write, registry)
            payload["written"] = args.write.name
            if not args.quiet:
                print(f"\n  written to {payload['written']}")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except StudentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
