"""Command line interface for the patient registry.

    python src/main.py --demo
    python src/main.py                       # the bundled 15 patients
    python src/main.py --stats
    python src/main.py --older-than 40
    python src/main.py --gender Female
    python src/main.py --diagnosis Diabetes
    python src/main.py --between 2025-01-12:2025-01-16
    python src/main.py --duplicates
    python src/main.py --legacy              # what the old reader saw
    python src/main.py --write clean.csv     # normalise to ISO dates
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from patients import (
    DATA_FILE,
    GENDERS,
    PatientError,
    admitted_between,
    age_summary,
    by_diagnosis,
    by_gender,
    dedupe,
    find_duplicates,
    older_than,
    read_csv,
    render_table,
    reread_legacy,
    run_demo,
    serial_to_date,
    stats,
    write_csv,
)

BANNER = """
====================================
 PATIENT ENTRY SYSTEM
   strict CSV, ISO dates, no Spark
====================================
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read, validate and query a patient CSV.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="patient CSV (default: data/patients.csv)")
    parser.add_argument("--older-than", type=int, metavar="AGE",
                        help="patients strictly older than AGE")
    parser.add_argument("--gender", choices=list(GENDERS),
                        help="patients of one gender")
    parser.add_argument("--diagnosis", metavar="NAME",
                        help="patients with one diagnosis")
    parser.add_argument("--between", metavar="START:END",
                        help="admissions within an inclusive ISO range")
    parser.add_argument("--stats", action="store_true",
                        help="counts, age summary and admission range")
    parser.add_argument("--duplicates", action="store_true",
                        help="report repeated patient ids instead of hiding them")
    parser.add_argument("--legacy", action="store_true",
                        help="show what the original reader saw")
    parser.add_argument("--write", type=Path, metavar="PATH",
                        help="write a normalised copy of the records")
    parser.add_argument("--json", type=Path, metavar="PATH",
                        help="write the result as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="write no standard output")
    args = parser.parse_args(argv)

    if args.demo:
        if args.quiet:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo()
        else:
            run_demo()
        return 0

    try:
        if args.legacy:
            legacy = reread_legacy()
            first = legacy["rows"][0] if legacy["rows"] else []
            payload = {
                "mode": "legacy",
                "header": legacy["header"],
                "names": len(legacy["header"]),
                "empty_name": legacy["header"][-1] == "",
                "rows": len(legacy["rows"]),
                "fields_per_row": len(first),
                "date_column": legacy["date_column"],
                "date_as_date": serial_to_date(
                    legacy["date_column"]).isoformat()
                if legacy["date_column"] else None,
                "seventh_column": legacy["seventh_column"],
            }
            if not args.quiet:
                print(BANNER)
                print(f"  header names       {payload['names']}")
                print(f"  last name is empty {payload['empty_name']}")
                print(f"  rows               {payload['rows']}")
                print(f"  fields per row     {payload['fields_per_row']}")
                print(f"  'AdmissionDate'    {payload['date_column']} "
                      f"-> {payload['date_as_date']}")
                print(f"  '' (seventh)       {payload['seventh_column']}")
                print("\n  the same date, twice, under two different "
                      "column names")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        patients = read_csv(args.file)
        payload: dict = {"file": args.file.name,
                         "patients": len(patients)}

        if args.older_than is not None:
            chosen = older_than(patients, args.older_than)
            payload.update({"mode": "older-than",
                            "age": args.older_than,
                            "rows": [patient.to_row() for patient in chosen],
                            "count": len(chosen)})
        elif args.gender:
            chosen = by_gender(patients, args.gender)
            payload.update({"mode": "gender", "gender": args.gender,
                            "rows": [patient.to_row() for patient in chosen],
                            "count": len(chosen)})
        elif args.diagnosis:
            chosen = by_diagnosis(patients, args.diagnosis)
            payload.update({"mode": "diagnosis",
                            "diagnosis": args.diagnosis,
                            "rows": [patient.to_row() for patient in chosen],
                            "count": len(chosen)})
        elif args.between:
            if ":" not in args.between:
                raise PatientError("expected START:END")
            start, end = args.between.split(":", 1)
            chosen = admitted_between(patients, start, end)
            payload.update({"mode": "between",
                            "start": start.strip(), "end": end.strip(),
                            "rows": [patient.to_row() for patient in chosen],
                            "count": len(chosen)})
        elif args.duplicates:
            found = find_duplicates(patients)
            payload.update({"mode": "duplicates",
                            "count": len(found),
                            "duplicates": [
                                {"patient_id": item.patient_id,
                                 "conflict": item.conflict,
                                 "extra": [patient.to_row()
                                           for patient in item.extra]}
                                for item in found]})
        elif args.stats:
            summary = stats(patients)
            payload.update({"mode": "stats", "stats": {
                "patients": summary["patients"],
                "genders": summary["genders"],
                "diagnoses": summary["diagnoses"],
                "ages": summary["ages"],
                "first_admission": summary["first_admission"].isoformat(),
                "last_admission": summary["last_admission"].isoformat(),
            }})
        else:
            payload.update({"mode": "list",
                            "rows": [patient.to_row() for patient in patients],
                            "stats": {"genders": stats(patients)["genders"],
                                      "ages": age_summary(patients)}})

        if args.write:
            write_csv(args.write, dedupe(patients))
            payload["written"] = args.write.name

        if not args.quiet:
            print(BANNER)
            if payload["mode"] in ("list", "older-than", "gender",
                                   "diagnosis", "between"):
                rows = payload["rows"]
                if rows:
                    from patients import Patient
                    print(render_table([Patient.from_row(row)
                                        for row in rows]))
                else:
                    print("  (no patients)")
                if payload["mode"] != "list":
                    print(f"\n  {payload['count']} record(s)")
            elif payload["mode"] == "duplicates":
                if payload["count"] == 0:
                    print("  no repeated patient ids")
                else:
                    for item in payload["duplicates"]:
                        kind = "conflicting" if item["conflict"] else "exact"
                        print(f"  patient {item['patient_id']}: "
                              f"{len(item['extra'])} extra row(s), {kind}")
            elif payload["mode"] == "stats":
                detail = payload["stats"]
                print(f"  patients     {detail['patients']}")
                print(f"  genders      {detail['genders']}")
                print(f"  ages         {detail['ages']}")
                print(f"  admissions   {detail['first_admission']} .. "
                      f"{detail['last_admission']}")
                for name, count in detail["diagnoses"].items():
                    print(f"    {name:<15} {count}")
            if payload["mode"] == "list":
                summary = payload["stats"]
                ages = summary["ages"]
                print(f"\n  {payload['patients']} patient(s), mean age "
                      f"{ages['mean']}, median {ages['median']}")
                print(f"  {summary['genders']}")
            if payload.get("written"):
                print(f"\n  written to {payload['written']}")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2, default=str),
                                 encoding="utf-8")
        return 0
    except PatientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
