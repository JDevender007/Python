"""Command line front end for the cloud cost lab.

Usage:
    python src/main.py --demo
    python src/main.py --demo --quiet
    python src/main.py --file data/bill.txt --json report.json
    python src/main.py --tier-units 550
    python src/main.py --audit
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cost_calculator import (                               # noqa: E402
    BILL_FILE,
    BUDGET_CENTS,
    TIERS,
    BillLine,
    DomainError,
    audit,
    bill_total,
    budget_status,
    disagreements,
    format_cents,
    format_price,
    legacy_bill_total,
    legacy_tiered_cents,
    measure,
    problems,
    read_bill,
    run_demo,
    tiered_cents,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloud-cost-lab",
        description="Price a monthly bill in integer cents, not floats.")
    parser.add_argument("--file", default=None, metavar="PATH",
                        help="a bill file (default: the bundled one)")
    parser.add_argument("--budget", default=BUDGET_CENTS, type=int,
                        metavar="CENTS",
                        help=f"the monthly budget in cents "
                             f"(default: {BUDGET_CENTS})")
    parser.add_argument("--tier-units", default=None, type=int, metavar="UNITS",
                        help="price this many units against the bundled tiers")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the bill and the measurements to PATH")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def _run_demo(quiet: bool) -> int:
    """Run the offline demo; with --quiet no stream prints anything."""
    if not quiet:
        return run_demo()
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        return run_demo()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet)
        except DomainError as error:
            if not args.quiet:
                print(f"error: {error}", file=sys.stderr)
            return 0

    try:
        lines = read_bill(args.file)
        budget_status(0, args.budget)
        if args.tier_units is not None:
            tiered_cents(args.tier_units)
    except DomainError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    total = bill_total(lines)
    legacy = legacy_bill_total(lines)
    differing = disagreements(lines)

    if not args.quiet:
        print(f"  {len(lines)} line(s) from "
              f"{args.file or BILL_FILE.name}")
        for row in lines:
            print(f"  {row.row()}")
        print(f"  total {format_cents(total)} ({total} cents), "
              f"legacy {format_cents(legacy)} ({legacy} cents), "
              f"{len(differing)} row(s) disagree")
        print(f"  budget {format_cents(args.budget)}: "
              f"{budget_status(total, args.budget)}")
        if args.tier_units is not None:
            print(f"  {args.tier_units} units -> "
                  f"{tiered_cents(args.tier_units)} cents tier by tier, "
                  f"{legacy_tiered_cents(args.tier_units)} cents at the "
                  f"marginal rate")

    checks = []
    failed: list[str] = []
    measured: dict = {}
    if args.audit:
        measured = measure(lines)
        checks = audit(measured, lines)
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "budget_cents": args.budget,
            "total_cents": total,
            "legacy_total_cents": legacy,
            "budget_status": budget_status(total, args.budget),
            "lines": [
                {
                    "service": row.service,
                    "sku": row.sku,
                    "quantity": row.quantity,
                    "price": format_price(row.price_tenths),
                    "price_tenths": row.price_tenths,
                    "cents": row.total_cents(),
                    "legacy_cents": row.legacy_cents(),
                }
                for row in lines
            ],
            "tiers": [
                {"width": width, "price_tenths": price}
                for width, price in TIERS
            ],
            "measurements": measured,
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the bill to {destination}")

    if failed:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
