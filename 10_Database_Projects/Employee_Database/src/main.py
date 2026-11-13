"""Command line entry point for the Employee Database.

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
    add_department,
    add_employee,
    deactivate_employee,
    department_salary_summary,
    get_employee,
    list_departments,
    list_employees,
    payroll_cost,
    search_employees,
    top_earners,
    update_salary,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("employee_db")

MENU = """
==============================
   EMPLOYEE DATABASE
==============================
 1) List employees
 2) List departments
 3) Add employee
 4) Search employee
 5) Update salary
 6) Deactivate employee
 7) Department salary report
 8) Top earners
 9) Payroll summary
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
    conn.execute("DELETE FROM employees WHERE employee_code = 'EMP900'")
    conn.execute("DELETE FROM departments WHERE name = 'Research'")
    conn.commit()


def run_demo(conn) -> None:
    """Non-interactive walkthrough used for smoke testing."""
    _reset_demo_rows(conn)

    print("== Department report ==")
    print(_rows(department_salary_summary(conn)))

    print("\n== Top earners ==")
    print(_rows(top_earners(conn, 3)))

    new_id = add_employee(
        conn,
        employee_code="EMP900",
        full_name="Demo User",
        email="demo.user@example.com",
        department_id=1,
        designation="Intern",
        salary=300_000,
        joined_on="2026-01-01",
    )
    print(f"\nInserted employee id={new_id}")

    update_salary(conn, new_id, 360_000)
    row = get_employee(conn, new_id)
    print(f"Updated salary -> {row['salary'] if row else 'n/a'}")

    deactivate_employee(conn, new_id)
    print("Deactivated demo employee")

    add_department(conn, "Research", "Building D")
    print("\n== Departments ==")
    print(_rows(list_departments(conn)))

    print("\n== Search 'demo' ==")
    print(_rows(search_employees(conn, "demo")))

    print("\n== Payroll summary ==")
    print("  " + ", ".join(f"{k}={v}" for k, v in payroll_cost(conn).items()))
    print("\nDemo completed successfully.")


def interactive(conn) -> None:
    """Simple numbered menu loop."""
    while True:
        print(MENU)
        choice = input("Select option: ").strip()
        try:
            if choice == "1":
                print(_rows(list_employees(conn)))
            elif choice == "2":
                print(_rows(list_departments(conn)))
            elif choice == "3":
                add_employee(
                    conn,
                    employee_code=input("  Code: "),
                    full_name=input("  Name: "),
                    email=input("  Email: "),
                    department_id=int(input("  Department id: ")),
                    designation=input("  Designation: "),
                    salary=float(input("  Salary: ")),
                    joined_on=input("  Joined (YYYY-MM-DD): "),
                )
                print("  Employee added.")
            elif choice == "4":
                print(_rows(search_employees(conn, input("  Search term: "))))
            elif choice == "5":
                update_salary(conn, int(input("  Employee id: ")), float(input("  New salary: ")))
                print("  Salary updated.")
            elif choice == "6":
                deactivate_employee(conn, int(input("  Employee id: ")))
                print("  Employee deactivated.")
            elif choice == "7":
                print(_rows(department_salary_summary(conn)))
            elif choice == "8":
                print(_rows(top_earners(conn)))
            elif choice == "9":
                print("  " + ", ".join(f"{k}={v}" for k, v in payroll_cost(conn).items()))
            elif choice == "0":
                print("Goodbye.")
                return
            else:
                print("  Unknown option.")
        except (ValueError, sqlite3.Error) as exc:
            print(f"  Error: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Employee Database CLI")
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
