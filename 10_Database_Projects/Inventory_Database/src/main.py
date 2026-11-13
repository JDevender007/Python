"""Command line entry point for the Inventory Database.

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
    add_product,
    add_supplier,
    category_summary,
    get_product,
    inventory_totals,
    list_products,
    list_suppliers,
    low_stock_report,
    movement_history,
    record_movement,
    search_products,
    stock_in,
    stock_out,
    update_price,
    valuation_report,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("inventory_db")

MENU = """
==============================
   INVENTORY DATABASE
==============================
 1) List products (with stock)
 2) List suppliers
 3) Search products
 4) Product details + history
 5) Add product
 6) Stock in
 7) Stock out
 8) Low stock alerts
 9) Valuation report
10) Category summary
11) Update price
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
    conn.execute(
        """
        DELETE FROM stock_movements
        WHERE product_id IN (SELECT id FROM products WHERE sku LIKE 'SKU900%')
        """
    )
    conn.execute("DELETE FROM products WHERE sku LIKE 'SKU900%'")
    conn.execute("DELETE FROM suppliers WHERE name = 'Demo Suppliers'")
    conn.commit()


def run_demo(conn) -> None:
    """Non-interactive walkthrough used for smoke testing."""
    _reset_demo_rows(conn)

    print("== Products with stock ==")
    print(_rows(list_products(conn)))

    print("\n== Stock IN: +30 of SKU1001 ==")
    stock_in(conn, 1, 30, note="Demo restock", created_on="2026-02-01")
    print(_rows(movement_history(conn, 1)))

    print("\n== Stock OUT: -5 of SKU1002 ==")
    stock_out(conn, 2, 5, note="Demo order", created_on="2026-02-02")
    print(f"  on_hand now = {get_product(conn, 2)['on_hand']}")

    print("\n== Insufficient stock guard ==")
    try:
        stock_out(conn, 6, 9999)
    except ValueError as exc:
        print(f"  correctly blocked: {exc}")

    new_id = add_product(
        conn,
        sku="SKU9001",
        name="Demo Gadget",
        category="Electronics",
        unit_price=125.0,
        supplier_id=1,
        reorder_level=5,
    )
    print(f"\nAdded product id={new_id}")
    update_price(conn, new_id, 149.0)
    print(f"Price updated -> {get_product(conn, new_id)['unit_price']}")

    add_supplier(conn, "Demo Suppliers", "+91-700", "demo@supplier.example", "Pune")
    print("\n== Suppliers ==")
    print(_rows(list_suppliers(conn)))

    print("\n== Search 'chair' ==")
    print(_rows(search_products(conn, "chair")))

    print("\n== Low stock alerts ==")
    print(_rows(low_stock_report(conn)))

    print("\n== Valuation ==")
    print(_rows(valuation_report(conn)))
    print("  Totals: " + ", ".join(f"{k}={v}" for k, v in inventory_totals(conn).items()))

    print("\n== Category summary ==")
    print(_rows(category_summary(conn)))
    print("\nDemo completed successfully.")


def interactive(conn) -> None:
    """Simple numbered menu loop."""
    while True:
        print(MENU)
        choice = input("Select option: ").strip()
        try:
            if choice == "1":
                print(_rows(list_products(conn)))
            elif choice == "2":
                print(_rows(list_suppliers(conn)))
            elif choice == "3":
                print(_rows(search_products(conn, input("  Search term: "))))
            elif choice == "4":
                pid = int(input("  Product id: "))
                row = get_product(conn, pid)
                print("  " + (", ".join(f"{k}={v}" for k, v in dict(row).items()) if row else "not found"))
                if row:
                    print(_rows(movement_history(conn, pid)))
            elif choice == "5":
                pid = add_product(
                    conn,
                    sku=input("  SKU: "),
                    name=input("  Name: "),
                    category=input("  Category: "),
                    unit_price=float(input("  Unit price: ")),
                    supplier_id=int(input("  Supplier id: ")),
                    reorder_level=int(input("  Reorder level [10]: ") or 10),
                )
                print(f"  Product id={pid} added.")
            elif choice == "6":
                stock_in(conn, int(input("  Product id: ")), int(input("  Quantity: ")),
                         note=input("  Note: "), created_on=input("  Date (YYYY-MM-DD): "))
                print("  Stock recorded.")
            elif choice == "7":
                stock_out(conn, int(input("  Product id: ")), int(input("  Quantity: ")),
                          note=input("  Note: "), created_on=input("  Date (YYYY-MM-DD): "))
                print("  Stock recorded.")
            elif choice == "8":
                print(_rows(low_stock_report(conn)))
            elif choice == "9":
                print(_rows(valuation_report(conn)))
            elif choice == "10":
                print(_rows(category_summary(conn)))
            elif choice == "11":
                print("  Updated." if update_price(conn, int(input("  Product id: ")),
                                                   float(input("  New price: "))) else "  Not found.")
            elif choice == "0":
                print("Goodbye.")
                return
            else:
                print("  Unknown option.")
        except (ValueError, sqlite3.Error) as exc:
            print(f"  Error: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inventory Database CLI")
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
