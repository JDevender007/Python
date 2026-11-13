"""Command line entry point for Attendance Management.

Usage
-----
    python src/main.py --demo          # scripted walkthrough, no input needed
    python src/main.py                 # interactive menu
    python src/main.py --db path.db    # use a custom database file
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

from database import open_initialised
from queries import (
    add_person,
    clear_day,
    csv_to_text,
    day_sheet,
    defaulters_report,
    export_csv,
    import_csv,
    list_people,
    mark_by_code,
    mark_attendance,
    monthly_report,
    search_people,
    status_summary,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("attendance")

MENU = """
==============================
   ATTENDANCE MANAGEMENT
==============================
 1) List people
 2) Search people
 3) Mark attendance
 4) Day sheet
 5) Clear a day
 6) Monthly report
 7) Defaulters (< 75%)
 8) Status summary
 9) Export CSV
10) Import CSV
 0) Exit
==============================
"""


def _rows(rows) -> str:
    """Render a list of sqlite3.Row objects as a padded text table."""
    if not rows:
        return "  (no rows)"
    data = [dict(r) for r in rows]
    headers = list(data[0].keys())
    widths = {h: max(len(str(h)), *(len(str(row[h])) for row in data)) for h in headers}
    line = "  " + " | ".join(h.ljust(widths[h]) for h in headers)
    sep = "  " + "-+-".join("-" * widths[h] for h in headers)
    body = "\n".join(
        "  " + " | ".join(str(row[h]).ljust(widths[h]) for h in headers) for row in data
    )
    return "\n".join([line, sep, body])


def _reset_demo_rows(conn) -> None:
    """Remove rows created by a previous demo run so the demo stays re-runnable."""
    conn.execute("DELETE FROM people WHERE code LIKE 'STU9%'")
    conn.execute("DELETE FROM attendance WHERE day = '2026-02-01'")
    conn.commit()


def run_demo(conn) -> None:
    """Non-interactive walkthrough used for smoke testing."""
    _reset_demo_rows(conn)

    print("== People ==")
    print(_rows(list_people(conn)))

    print("\n== Day sheet 2026-01-06 ==")
    print(_rows(day_sheet(conn, "2026-01-06")))

    new_id = add_person(conn, "STU901", "Demo Student", "Batch C")
    print(f"\nRegistered person id={new_id}")

    mark_attendance(conn, new_id, "2026-02-01", "present", "demo")
    mark_by_code(conn, "STU901", "2026-02-02", "late", "demo")
    print("Marked 2026-02-01 present, 2026-02-02 late")

    # upsert: re-marking the same day must update, not duplicate
    mark_attendance(conn, new_id, "2026-02-01", "absent", "changed my mind")
    sheet = day_sheet(conn, "2026-02-01")
    print("Upsert check -> " + ", ".join(
        f"{r['code']}={r['status']}" for r in sheet if r["code"] == "STU901"
    ))

    print("\n== Monthly report 2026-01 ==")
    print(_rows(monthly_report(conn, "2026-01")))

    print("\n== Defaulters (< 75%) ==")
    print(_rows(defaulters_report(conn, "2026-01", 75.0)))

    print("\n== Status summary (2026-01-06) ==")
    print("  " + ", ".join(f"{k}={v}" for k, v in status_summary(conn, "2026-01-06").items()))

    csv_path = Path(__file__).resolve().parent.parent / "data" / "attendance_export.csv"
    export_csv(conn, csv_path, month="2026-01")
    print(f"\nExported {csv_path.name}")
    imported = import_csv(conn, csv_path)
    print(f"Re-imported {imported} rows (upsert, no duplicates)")

    print("\n== Search 'batch c' ==")
    print(_rows(search_people(conn, "batch c")))

    cleared = clear_day(conn, "2026-02-01")
    print(f"\nCleared {cleared} row(s) for 2026-02-01")
    print("\nDemo completed successfully.")


def interactive(conn) -> None:
    """Simple numbered menu loop."""
    while True:
        print(MENU)
        choice = input("Select option: ").strip()
        try:
            if choice == "1":
                print(_rows(list_people(conn)))
            elif choice == "2":
                print(_rows(search_people(conn, input("  Search term: "))))
            elif choice == "3":
                code = input("  Person code: ")
                day = input("  Date (YYYY-MM-DD): ")
                status = input("  Status (present/absent/late/leave): ")
                print(f"  {mark_by_code(conn, code, day, status, input('  Note: '))}.")
            elif choice == "4":
                print(_rows(day_sheet(conn, input("  Date (YYYY-MM-DD): "))))
            elif choice == "5":
                print(f"  Deleted {clear_day(conn, input('  Date (YYYY-MM-DD): '))} row(s).")
            elif choice == "6":
                print(_rows(monthly_report(conn, input("  Month (YYYY-MM): "))))
            elif choice == "7":
                month = input("  Month (YYYY-MM): ")
                threshold = float(input("  Threshold [75]: ") or 75)
                print(_rows(defaulters_report(conn, month, threshold)))
            elif choice == "8":
                print("  " + ", ".join(
                    f"{k}={v}" for k, v in status_summary(conn, input("  Date (YYYY-MM-DD, blank=all): ") or None).items()
                ))
            elif choice == "9":
                path = export_csv(conn, input("  Output path: "), input("  Month filter (YYYY-MM, blank=all): ") or None)
                print(f"  Exported {path}")
            elif choice == "10":
                print(f"  Imported {import_csv(conn, input('  CSV path: '))} rows.")
            elif choice == "0":
                print("Goodbye.")
                return
            else:
                print("  Unknown option.")
        except (ValueError, sqlite3.Error, FileNotFoundError) as exc:
            print(f"  Error: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Attendance Management CLI")
    parser.add_argument("--demo", action="store_true", help="run a scripted demo and exit")
    parser.add_argument("--db", type=Path, default=None, help="path to the SQLite database")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    conn = open_initialised(args.db)
    try:
        if args.demo:
            run_demo(conn)
        else:
            interactive(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
