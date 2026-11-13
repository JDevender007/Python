"""Command line entry point for the Hospital Database.

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
    add_doctor,
    add_patient,
    book_appointment,
    create_bill,
    discharge_patient,
    get_patient,
    list_appointments,
    list_doctors,
    pay_bill,
    revenue_report,
    revenue_totals,
    schedule_view,
    search_patients,
    set_appointment_status,
    specialty_workload,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("hospital_db")

MENU = """
==============================
   HOSPITAL DATABASE
==============================
 1) List doctors
 2) Search patients
 3) Patient details + balance
 4) Book appointment
 5) Today's / day schedule
 6) Complete appointment (discharge)
 7) Cancel appointment
 8) Issue bill
 9) Pay bill
10) Revenue report
11) Specialty workload
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
    """Remove rows created by a previous demo run so the demo stays re-runnable.

    Deleting the demo patient cascades to their appointments and bills.
    """
    conn.execute("DELETE FROM patients WHERE mrn = 'MRN9001'")
    conn.commit()


def run_demo(conn) -> None:
    """Non-interactive walkthrough used for smoke testing."""
    _reset_demo_rows(conn)

    print("== Doctors ==")
    print(_rows(list_doctors(conn)))

    print("\n== Schedule 2026-01-06 ==")
    print(_rows(schedule_view(conn, "2026-01-06")))

    patient_id = add_patient(
        conn,
        mrn="MRN9001",
        full_name="Demo Patient",
        date_of_birth="1990-08-08",
        gender="Other",
        phone="+91-999999999",
        blood_group="O-",
    )
    print(f"\nRegistered patient id={patient_id}")

    appt_id = book_appointment(
        conn,
        patient_id=patient_id,
        doctor_id=1,
        scheduled_on="2026-01-08",
        slot="14:00",
        reason="Demo consultation",
    )
    print(f"Booked appointment id={appt_id}")

    discharge_patient(conn, appt_id)
    print("Discharged (appointment completed)")

    bill_id = create_bill(conn, patient_id=patient_id, amount=1250.0, issued_on="2026-01-08",
                          appointment_id=appt_id)
    pay_bill(conn, bill_id)
    print(f"Issued and paid bill id={bill_id}")

    row = get_patient(conn, patient_id)
    print(f"Patient balance due: {row['balance_due'] if row else 'n/a'}")

    print("\n== Search 'demo' ==")
    print(_rows(search_patients(conn, "demo")))

    print("\n== Revenue by day ==")
    print(_rows(revenue_report(conn)))
    print("  Totals: " + ", ".join(f"{k}={v}" for k, v in revenue_totals(conn).items()))

    print("\n== Specialty workload ==")
    print(_rows(specialty_workload(conn)))
    print("\nDemo completed successfully.")


def interactive(conn) -> None:
    """Simple numbered menu loop."""
    while True:
        print(MENU)
        choice = input("Select option: ").strip()
        try:
            if choice == "1":
                print(_rows(list_doctors(conn)))
            elif choice == "2":
                print(_rows(search_patients(conn, input("  Search term: "))))
            elif choice == "3":
                row = get_patient(conn, int(input("  Patient id: ")))
                print("  " + (", ".join(f"{k}={v}" for k, v in dict(row).items()) if row else "not found"))
            elif choice == "4":
                appt_id = book_appointment(
                    conn,
                    patient_id=int(input("  Patient id: ")),
                    doctor_id=int(input("  Doctor id: ")),
                    scheduled_on=input("  Date (YYYY-MM-DD): "),
                    slot=input("  Slot (HH:MM): "),
                    reason=input("  Reason: "),
                )
                print(f"  Appointment id={appt_id} booked.")
            elif choice == "5":
                print(_rows(schedule_view(conn, input("  Date (YYYY-MM-DD): "))))
            elif choice == "6":
                print("  Updated." if discharge_patient(conn, int(input("  Appointment id: "))) else "  Not found.")
            elif choice == "7":
                print("  Updated." if set_appointment_status(conn, int(input("  Appointment id: ")), "cancelled")
                      else "  Not found.")
            elif choice == "8":
                bill_id = create_bill(
                    conn,
                    patient_id=int(input("  Patient id: ")),
                    amount=float(input("  Amount: ")),
                    issued_on=input("  Issued (YYYY-MM-DD): "),
                )
                print(f"  Bill id={bill_id} issued.")
            elif choice == "9":
                print("  Paid." if pay_bill(conn, int(input("  Bill id: "))) else "  Not found.")
            elif choice == "10":
                print(_rows(revenue_report(conn)))
            elif choice == "11":
                print(_rows(specialty_workload(conn)))
            elif choice == "0":
                print("Goodbye.")
                return
            else:
                print("  Unknown option.")
        except (ValueError, sqlite3.Error) as exc:
            print(f"  Error: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hospital Database CLI")
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
