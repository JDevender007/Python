"""Command line front end for the price lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prices import (                                        # noqa: E402
    PriceError,
    audit,
    change_bp,
    format_bp,
    legacy_clean_price,
    legacy_display,
    legacy_offer_price,
    parse_offer,
    parse_price,
    parse_range,
    problems,
    read_offer_page,
    read_watch,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="price-lab",
        description="Read money out of price text as integer cents, keep a "
                    "range a range, and never report an unknown price as "
                    "zero.")
    parser.add_argument("--page", default=None, metavar="PATH",
                        help="a product page to read (default: the bundled "
                             "one)")
    parser.add_argument("--watch", default=None, metavar="PATH",
                        help="a tick<TAB>price log (default: the bundled one)")
    parser.add_argument("--price", default=None, metavar="TEXT",
                        help="read one price and print its cents")
    parser.add_argument("--range", dest="range_text", default=None,
                        metavar="TEXT", help="read a price range")
    parser.add_argument("--target", default=None, metavar="AMOUNT",
                        help="report the days at or below this price")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the reading to PATH as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    if args.price is not None:
        try:
            money = parse_price(args.price)
        except PriceError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"  {args.price!r} is {money.format()} = {money.cents} "
                  f"cents of {money.currency}")
            print(f"  the legacy cleaner says "
                  f"{legacy_clean_price(args.price):.4f}, as a bare float")
        return 0

    if args.range_text is not None:
        try:
            low, high = parse_range(args.range_text)
        except PriceError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            shown = [money.format() if money else "unknown"
                     for money in (low, high)]
            print(f"  {args.range_text!r} is a range from {shown[0]} to "
                  f"{shown[1]}")
        return 0

    try:
        page = read_offer_page(args.page)
        offer = parse_offer(page)
        watch = read_watch(args.watch)
    except PriceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    target = None
    if args.target:
        try:
            target = parse_price(args.target)
        except PriceError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2

    if not args.quiet:
        print(f"  {offer.title}")
        print(f"  the buy box says "
              f"{offer.price.format() if offer.price else 'nothing readable'}")
        if offer.price is None:
            print(f"  why: {offer.note}")
        print(f"  the first .a-offscreen says "
              f"{legacy_display(legacy_offer_price(page))}")
        print(f"  the list price is "
              f"{offer.list_price.format() if offer.list_price else 'unknown'}")
        print(f"  change from the list price: "
              f"{format_bp(offer.discount_bp())}")

        print(f"  {len(watch)} sample(s), first {watch.first().price.format()} "
              f"at t={watch.first().at}, last {watch.last().price.format()} "
              f"at t={watch.last().at}")
        print(f"  lowest {watch.lowest().price.format()} at "
              f"t={watch.lowest().at}")
        print(f"  change from the first sample: {format_bp(watch.change())}")

        if target is not None:
            hits = watch.below(target)
            first = watch.first_below(target)
            print(f"  at or below {target.format()}: {len(hits)} day(s)"
                  + (f", first at t={first.at}" if first else ""))

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        checks = audit(offer, watch, page)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "title": offer.title,
            "buy_box": None if offer.price is None else {
                "cents": offer.price.cents,
                "currency": offer.price.currency,
                "text": offer.price.format(),
            },
            "first_offscreen": legacy_offer_price(page),
            "list_price": None if offer.list_price is None else
            offer.list_price.cents,
            "availability": offer.availability,
            "note": offer.note,
            "change_from_list": offer.discount_bp(),
            "watch": [{"at": sample.at, "cents": sample.price.cents}
                      for sample in watch.samples],
            "lowest": {"at": watch.lowest().at,
                       "cents": watch.lowest().price.cents},
            "change": watch.change(),
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the reading to {destination}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
