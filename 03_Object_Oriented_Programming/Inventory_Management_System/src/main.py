"""Command line interface for the inventory.

    python src/main.py --demo
    python src/main.py                                  # every line
    python src/main.py --search widget
    python src/main.py --low-stock
    python src/main.py --add "P-600:Plunger:Hardware:4.25:25:Acme"
    python src/main.py --stock-in W-100:5
    python src/main.py --stock-out G-200:12
    python src/main.py --remove P-600
    python src/main.py --value
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

from inventory import (
    DATA_FILE,
    LEGACY_PRICE,
    LEGACY_SEARCH,
    LEGACY_STOCK_IN,
    LOW_STOCK,
    DuplicateItem,
    Inventory,
    InventoryError,
    Item,
    NotEnoughStock,
    UnknownItem,
    format_cents,
    load_inventory,
    run_demo,
    save_inventory,
)

BANNER = """
========================================
 INVENTORY
   SKUs, quantities, a live total
========================================
"""


def _split(spec: str, low: int, high: int, shape: str) -> list[str]:
    pieces = [piece.strip() for piece in spec.split(":")]
    if not low <= len(pieces) <= high or not all(pieces):
        raise InventoryError(f"expected {shape}, got {spec!r}")
    return pieces


def _units(text: str) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        raise InventoryError(f"{text!r} is not a whole number of units") \
            from None


def _price(text: str) -> int:
    """``4.25`` -> 425, refusing more than two decimal places."""
    cleaned = text.strip().replace(",", "")
    if not cleaned:
        raise InventoryError("the price is empty")
    if cleaned.startswith("-"):
        raise InventoryError("a price must not be negative")
    if "." in cleaned:
        whole, _, fraction = cleaned.partition(".")
        if len(fraction) > 2 or not fraction:
            raise InventoryError(f"{text!r} has more than two decimal places")
        if not whole:
            whole = "0"
        if not (whole.isdigit() and fraction.isdigit()):
            raise InventoryError(f"{text!r} is not a number")
        return int(whole) * 100 + int(fraction.ljust(2, "0"))
    if not cleaned.isdigit():
        raise InventoryError(f"{text!r} is not a number")
    return int(cleaned) * 100


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="An inventory whose objects behave like values.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="inventory file (default: data/inventory.json)")
    parser.add_argument("--items", action="store_true",
                        help="one line per SKU (the default)")
    parser.add_argument("--search", metavar="TEXT",
                        help="every line matching SKU, name, category, supplier")
    parser.add_argument("--low-stock", metavar="N", type=int, nargs="?",
                        const=LOW_STOCK, default=None,
                        help=f"lines at or below N units (default {LOW_STOCK})")
    parser.add_argument("--add", metavar="SKU:NAME:CATEGORY:PRICE:QTY[:SUPPLIER]",
                        help="stock a new item")
    parser.add_argument("--stock-in", metavar="SKU:UNITS",
                        help="add units to a line")
    parser.add_argument("--stock-out", metavar="SKU:UNITS",
                        help="remove units from a line")
    parser.add_argument("--remove", metavar="SKU", help="drop a line")
    parser.add_argument("--value", action="store_true",
                        help="the total, and a breakdown by category")
    parser.add_argument("--audit", action="store_true",
                        help="run the five invariants")
    parser.add_argument("--legacy", action="store_true",
                        help="show the legacy defects the demo proves")
    parser.add_argument("--write", type=Path, metavar="PATH",
                        help="save the inventory after the change")
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
            payload = {
                "mode": "legacy",
                "price": LEGACY_PRICE,
                "movement": LEGACY_STOCK_IN,
                "search": LEGACY_SEARCH,
                "note": "stock_in(-5) subtracts; stock_out(-5) adds",
            }
            if not args.quiet:
                print(BANNER)
                print(f"  price     {LEGACY_PRICE}")
                print(f"  movement  {LEGACY_STOCK_IN}   (no check)")
                print(f"  search    {LEGACY_SEARCH}   (one row only)")
                print(f"  {payload['note']}")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        inventory = load_inventory(args.file)
        payload: dict = {"mode": "items", "inventory": inventory.name,
                         "total_cents": inventory.value()}

        if args.search is not None:
            lines = inventory.search(args.search)
            payload = {"mode": "search", "needle": args.search,
                       "found": [line.item.sku for line in lines],
                       "count": len(lines)}
            if not args.quiet:
                print(BANNER)
                for line in lines:
                    print(f"  {line}")
                print(f"\n  {len(lines)} line(s) match {args.search!r}")
        elif args.low_stock is not None:
            lines = inventory.low_stock(args.low_stock)
            payload = {"mode": "low_stock", "threshold": args.low_stock,
                       "skus": [line.item.sku for line in lines],
                       "count": len(lines)}
            if not args.quiet:
                print(BANNER)
                for line in lines:
                    print(f"  {line}")
                print(f"\n  {len(lines)} line(s) at or below "
                      f"{args.low_stock} units")
        elif args.add:
            pieces = _split(args.add, 5, 6,
                            "SKU:NAME:CATEGORY:PRICE:QTY[:SUPPLIER]")
            supplier = pieces[5] if len(pieces) == 6 else ""
            item = Item(pieces[0], pieces[1], pieces[2], _price(pieces[3]),
                        supplier)
            line = inventory.add(item, _units(pieces[4]))
            payload = {"mode": "add", "sku": line.item.sku,
                       "quantity": line.quantity,
                       "price_cents": line.item.price,
                       "value_cents": line.value}
            if not args.quiet:
                print(BANNER)
                print(f"  added {line.item.sku}  {line.item.name}  "
                      f"x{line.quantity} at {format_cents(line.item.price)}")
        elif args.stock_in:
            sku, units = _split(args.stock_in, 2, 2, "SKU:UNITS")
            line = inventory.stock_in(sku, _units(units))
            payload = {"mode": "stock_in", "sku": line.item.sku,
                       "quantity": line.quantity}
            if not args.quiet:
                print(BANNER)
                print(f"  {line.item.sku} now holds {line.quantity}")
        elif args.stock_out:
            sku, units = _split(args.stock_out, 2, 2, "SKU:UNITS")
            line = inventory.stock_out(sku, _units(units))
            payload = {"mode": "stock_out", "sku": line.item.sku,
                       "quantity": line.quantity}
            if not args.quiet:
                print(BANNER)
                print(f"  {line.item.sku} now holds {line.quantity}")
        elif args.remove:
            line = inventory.remove(args.remove)
            payload = {"mode": "remove", "sku": line.item.sku,
                       "removed": line.quantity}
            if not args.quiet:
                print(BANNER)
                print(f"  removed {line.item.sku} ({line.quantity} units)")
        elif args.value:
            payload = {"mode": "value", "total_cents": inventory.value(),
                       "total": format_cents(inventory.value()),
                       "by_category": inventory.by_category()}
            if not args.quiet:
                print(BANNER)
                for category, cents in inventory.by_category().items():
                    print(f"  {category:<14} {format_cents(cents):>14}")
                print(f"  {'total':<14} {format_cents(inventory.value()):>14}")
        elif args.audit:
            checks = inventory.audit()
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
            payload = {"mode": "items",
                       "lines": [{"sku": line.item.sku,
                                  "name": line.item.name,
                                  "category": line.item.category,
                                  "price_cents": line.item.price,
                                  "quantity": line.quantity,
                                  "value_cents": line.value}
                                 for line in inventory]}
            if not args.quiet:
                print(BANNER)
                for line in inventory:
                    print(f"  {line}")
                print(f"\n  {len(inventory)} line(s), "
                      f"{format_cents(inventory.value())}")

        if args.write:
            save_inventory(args.write, inventory)
            payload["written"] = args.write.name
            if not args.quiet:
                print(f"\n  written to {payload['written']}")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except (InventoryError, DuplicateItem, UnknownItem, NotEnoughStock) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
