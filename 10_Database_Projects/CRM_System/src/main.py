"""Command line entry point for the CRM System.

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
    add_customer,
    add_deal,
    add_lead,
    convert_lead,
    follow_ups,
    get_customer,
    interaction_history,
    kpi_summary,
    lead_funnel,
    list_customers,
    list_leads,
    log_interaction,
    move_deal,
    pipeline_summary,
    search_customers,
    top_customers,
    update_lead_status,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("crm")

MENU = """
==============================
   CRM SYSTEM
==============================
 1) List customers
 2) Search customers
 3) Customer details
 4) Add customer
 5) Add lead
 6) Update lead status
 7) Convert lead
 8) Log interaction
 9) Interaction history
10) Follow-ups (closing soon)
11) Pipeline summary
12) Lead funnel
13) KPI summary
14) Top customers
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
    conn.execute("DELETE FROM leads WHERE email LIKE '%@demo.example'")
    conn.execute("DELETE FROM customers WHERE email LIKE '%@demo.example'")
    conn.commit()


def run_demo(conn) -> None:
    """Non-interactive walkthrough used for smoke testing."""
    _reset_demo_rows(conn)

    print("== Customers ==")
    print(_rows(list_customers(conn)))

    print("\n== Lead funnel ==")
    print(_rows(lead_funnel(conn)))

    lead_id = add_lead(
        conn,
        name="Demo Prospect",
        email="prospect@demo.example",
        source="website",
        score=75,
        created_on="2026-02-01",
    )
    print(f"\nAdded lead id={lead_id}")
    update_lead_status(conn, lead_id, "contacted")
    update_lead_status(conn, lead_id, "qualified")
    print("Moved lead: new -> contacted -> qualified")

    customer_id = convert_lead(conn, lead_id, phone="+91-700", company="Demo Co")
    print(f"Converted lead -> customer id={customer_id}")

    log_interaction(conn, customer_id, "call", "Discovery call booked", "2026-02-02")
    log_interaction(conn, customer_id, "email", "Sent proposal", "2026-02-03")
    print("Logged 2 interactions")

    deal_id = add_deal(
        conn, customer_id=customer_id, title="Demo Co pilot",
        value=50000.0, stage="proposal", close_on="2099-12-31",
    )
    print(f"Created deal id={deal_id}")
    move_deal(conn, deal_id, "won")
    print("Deal moved to 'won'")

    print("\n== Pipeline ==")
    print(_rows(pipeline_summary(conn)))

    print("\n== Follow-ups (next 30 days) ==")
    print(_rows(follow_ups(conn, days=30)))

    print("\n== Interaction history (customer) ==")
    print(_rows(interaction_history(conn, customer_id)))

    print("\n== Customer details ==")
    row = get_customer(conn, customer_id)
    print("  " + ", ".join(f"{k}={v}" for k, v in dict(row).items()))

    print("\n== Search 'demo' ==")
    print(_rows(search_customers(conn, "demo")))

    print("\n== Top customers ==")
    print(_rows(top_customers(conn)))

    print("\n== KPIs ==")
    print("  " + ", ".join(f"{k}={v}" for k, v in kpi_summary(conn).items()))
    print("\nDemo completed successfully.")


def interactive(conn) -> None:
    """Simple numbered menu loop."""
    while True:
        print(MENU)
        choice = input("Select option: ").strip()
        try:
            if choice == "1":
                print(_rows(list_customers(conn)))
            elif choice == "2":
                print(_rows(search_customers(conn, input("  Search term: "))))
            elif choice == "3":
                row = get_customer(conn, int(input("  Customer id: ")))
                print("  " + (", ".join(f"{k}={v}" for k, v in dict(row).items()) if row else "not found"))
            elif choice == "4":
                cid = add_customer(
                    conn,
                    name=input("  Name: "),
                    email=input("  Email: "),
                    phone=input("  Phone: "),
                    company=input("  Company: "),
                )
                print(f"  Customer id={cid}.")
            elif choice == "5":
                lead_id = add_lead(
                    conn,
                    name=input("  Name: "),
                    email=input("  Email: "),
                    source=input("  Source [inbound]: ") or "inbound",
                    score=int(input("  Score [0]: ") or 0),
                )
                print(f"  Lead id={lead_id}.")
            elif choice == "6":
                print("  Updated." if update_lead_status(conn, int(input("  Lead id: ")),
                                                         input("  New status: ")) else "  Not found.")
            elif choice == "7":
                cid = convert_lead(conn, int(input("  Lead id: ")),
                                   phone=input("  Phone: "), company=input("  Company: "))
                print(f"  Converted -> customer id={cid}" if cid else "  Lead not found.")
            elif choice == "8":
                iid = log_interaction(
                    conn,
                    int(input("  Customer id: ")),
                    input("  Kind (call/email/meeting/note): "),
                    input("  Summary: "),
                )
                print(f"  Interaction id={iid}.")
            elif choice == "9":
                print(_rows(interaction_history(conn, int(input("  Customer id: ")))))
            elif choice == "10":
                print(_rows(follow_ups(conn, int(input("  Days ahead [7]: ") or 7))))
            elif choice == "11":
                print(_rows(pipeline_summary(conn)))
            elif choice == "12":
                print(_rows(lead_funnel(conn)))
            elif choice == "13":
                print("  " + ", ".join(f"{k}={v}" for k, v in kpi_summary(conn).items()))
            elif choice == "14":
                print(_rows(top_customers(conn)))
            elif choice == "0":
                print("Goodbye.")
                return
            else:
                print("  Unknown option.")
        except (ValueError, sqlite3.Error) as exc:
            print(f"  Error: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CRM System CLI")
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
