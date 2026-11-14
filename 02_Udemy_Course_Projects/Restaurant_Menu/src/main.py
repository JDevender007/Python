"""Command line interface for the menu and cart.

    python src/main.py --demo
    python src/main.py                       # the printed menu
    python src/main.py --stats
    python src/main.py --price "Pad Thai"
    python src/main.py --order "Pad Thai:2" --order Lemonade
    python src/main.py --legacy "Pad Thai:12"
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from menu import (
    DATA_FILE,
    MENU_WIDTH,
    TAX_BASIS_POINTS,
    Cart,
    MenuError,
    display_width,
    dot_leader,
    find_item,
    format_price,
    legacy_line,
    load_menu,
    parse_price,
    render_menu,
    run_demo,
    stats,
    tax_for,
    write_menu,
)

BANNER = """
====================================
 RESTAURANT MENU
   dot leaders, cents, a cart
====================================
"""


def _split_pair(value: str) -> tuple[str, int]:
    """``DISH:QTY`` with the quantity optional, defaulting to one."""
    if ":" not in value:
        name = value.strip()
        if not name:
            raise MenuError(f"expected DISH:QUANTITY, got {value!r}")
        return name, 1
    name, quantity = value.rsplit(":", 1)
    name = name.strip()
    if not name:
        raise MenuError(f"expected DISH:QUANTITY, got {value!r}")
    try:
        amount = int(quantity.strip())
    except ValueError:
        raise MenuError(f"quantity {quantity.strip()!r} is not a whole number") \
            from None
    return name, amount


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print a menu, price a dish, build a cart.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="menu file (default: data/menu.csv)")
    parser.add_argument("--stats", action="store_true",
                        help="dish count and price extremes")
    parser.add_argument("--price", metavar="DISH",
                        help="look one dish up")
    parser.add_argument("--order", metavar="DISH:QTY", action="append",
                        default=[], help="add a line to the cart")
    parser.add_argument("--legacy", metavar="DISH:PRICE",
                        help="print the original formatter's line")
    parser.add_argument("--width", type=int, default=MENU_WIDTH,
                        help="line width for the printed menu")
    parser.add_argument("--tax-rate", type=float, metavar="PERCENT",
                        help="tax rate as a percentage (default 8.75)")
    parser.add_argument("--write", type=Path, metavar="PATH",
                        help="write the menu back out in canonical form")
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
        if args.width < 1:
            raise MenuError("width must be at least 1")
        basis_points = TAX_BASIS_POINTS
        if args.tax_rate is not None:
            basis_points = int(round(args.tax_rate * 100))
            if not 0 <= basis_points <= 10000:
                raise MenuError("tax rate must be between 0 and 100 percent")

        if args.legacy is not None:
            if ":" not in args.legacy:
                raise MenuError("expected DISH:PRICE")
            dish, price = args.legacy.rsplit(":", 1)
            dish = dish.strip()
            try:
                dollars = int(price.strip())
            except ValueError:
                raise MenuError(
                    f"the legacy program only accepted whole dollars, "
                    f"got {price.strip()!r}") from None
            line = legacy_line(dish, dollars)
            payload = {"mode": "legacy", "dish": dish,
                       "price": dollars, "line": line,
                       "gap": len(line) - len(dish) - len(f"${dollars}")}
            if not args.quiet:
                print(BANNER)
                print(f"  line   {line!r}")
                print(f"  gap    {payload['gap']} dash(es)")
                if payload["gap"] <= 0:
                    print("  note: '-' * 0 is '', so the price sits "
                          "straight against the dish name")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        menu = load_menu(args.file)
        payload: dict = {"file": args.file.name, "dishes": len(menu),
                         "tax_basis_points": basis_points}

        if args.price:
            item = find_item(menu, args.price)
            payload.update({"mode": "price", "dish": item.name,
                            "price_cents": item.price_cents,
                            "price": format_price(item.price_cents)})
            if not args.quiet:
                print(BANNER)
                print(f"  {item.name:<24} {format_price(item.price_cents):>8}")
        elif args.order:
            cart = Cart(menu)
            for spec in args.order:
                name, quantity = _split_pair(spec)
                cart.add(name, quantity)
            tax = tax_for(cart.subtotal(), basis_points)
            total = cart.subtotal() + tax
            payload.update({"mode": "order",
                            "lines": [{"name": item.name, "quantity": quantity,
                                       "price_cents": item.price_cents,
                                       "line_cents": item.price_cents * quantity}
                                      for item, quantity in cart.lines],
                            "items": cart.items,
                            "subtotal_cents": cart.subtotal(),
                            "tax_cents": tax,
                            "total_cents": total,
                            "subtotal": format_price(cart.subtotal()),
                            "tax": format_price(tax),
                            "total": format_price(total)})
            if not args.quiet:
                print(BANNER)
                for item, quantity in cart.lines:
                    label = f"{quantity} x {item.name}"
                    print(dot_leader(label, item.price_cents * quantity,
                                     args.width))
                print("-" * args.width)
                print(dot_leader("Subtotal", cart.subtotal(), args.width))
                print(dot_leader(f"Tax ({basis_points / 100:g}%)", tax,
                                 args.width))
                print(dot_leader("Total", total, args.width))
        elif args.stats:
            summary = stats(menu)
            payload.update({"mode": "stats",
                            "cheapest": summary["cheapest"],
                            "cheapest_dish": min(menu,
                                                 key=lambda item:
                                                 item.price_cents).name,
                            "dearest": summary["dearest"],
                            "dearest_dish": max(menu,
                                                key=lambda item:
                                                item.price_cents).name,
                            "average_cents": summary["average"]})
            if not args.quiet:
                print(BANNER)
                print(f"  dishes     {summary['dishes']}")
                print(f"  cheapest   {format_price(summary['cheapest'])} "
                      f"({payload['cheapest_dish']})")
                print(f"  dearest    {format_price(summary['dearest'])} "
                      f"({payload['dearest_dish']})")
                print(f"  average    {format_price(summary['average'])}")
        else:
            payload.update({"mode": "menu",
                            "items": [{"name": item.name,
                                       "price_cents": item.price_cents}
                                      for item in menu],
                            "width": args.width})
            if not args.quiet:
                print(BANNER)
                print(render_menu(menu, args.width))
                print(f"\n  {len(menu)} dishes")

        if args.write:
            write_menu(args.write, menu)
            payload["written"] = args.write.name
            if not args.quiet:
                print(f"\n  written to {payload['written']}")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except MenuError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
