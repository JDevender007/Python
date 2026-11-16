"""Command line front end for the rate lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rates import (                                         # noqa: E402
    FRESH_DAYS,
    READ_ON,
    RateError,
    audit,
    legacy_convert,
    legacy_rate,
    legacy_table,
    parse_amounts,
    problems,
    read_amounts,
    read_sheet,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rate-lab",
        description="Convert money with a rate that has a direction and a day, "
                    "in integers only, and never at par.")
    parser.add_argument("--quote", default=None, metavar="PATH",
                        help="a rate sheet (default: the bundled one)")
    parser.add_argument("--amounts", default=None, metavar="PATH",
                        help="a list of amounts (default: the bundled one)")
    parser.add_argument("--on", default=READ_ON, metavar="YYYY-MM-DD",
                        help=f"the day the sheet is read (default: {READ_ON})")
    parser.add_argument("--limit", default=FRESH_DAYS, type=int, metavar="DAYS",
                        help=f"how long a quote stays fresh (default: "
                             f"{FRESH_DAYS})")
    parser.add_argument("--convert", default=None, metavar="TEXT",
                        help="convert an amount, e.g. '100.00 USD to EUR'")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the reading to PATH as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def _parse_convert(text: str) -> tuple[str, str, str]:
    """`100.00 USD to EUR` -> `("USD", "100.00", "EUR")`, unparsed and unsplit."""
    words = text.replace("->", " to ").split()
    if len(words) != 4 or words[2].lower() != "to":
        raise RateError("a conversion reads 'AMOUNT CODE to CODE', e.g. "
                        "'100.00 USD to EUR'")
    amount_text, source, _, target = words
    return source.upper(), amount_text, target.upper()


def _minor(amount_text: str, code: str, exponent: int) -> int:
    """`100.00` in a currency with two places -> 10000 minor units."""
    negative = amount_text.startswith("-")
    body = amount_text.lstrip("+-")
    whole, _, fraction = body.partition(".")
    if not whole.isdigit() or (fraction and not fraction.isdigit()) or \
            body.count(".") > 1:
        raise RateError(f"{amount_text!r} is not an amount")
    if len(fraction) > exponent:
        raise RateError(f"{code} has {exponent} decimal place(s), so "
                        f"{amount_text!r} is too precise")
    digits = int(fraction.ljust(exponent, "0")) if exponent else 0
    minor = int(whole) * 10 ** exponent + digits
    return -minor if negative else minor


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        on = date.fromisoformat(args.on)
    except ValueError:
        print(f"error: {args.on!r} is not a day written YYYY-MM-DD",
              file=sys.stderr)
        return 2

    try:
        sheet = read_sheet(args.quote)
    except RateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.convert is not None:
        try:
            source, amount_text, target = _parse_convert(args.convert)
            minor = _minor(amount_text, source, sheet.exponent(source))
            base = sheet.quote.base
            if source == base and target == base:
                raise RateError(f"{base} to {base} needs no rate")
            if source == base:
                converted = sheet.convert(minor, target)
            elif target == base:
                converted = sheet.convert_back(minor, source)
            else:
                raise RateError(f"this lab converts from {base} or to it, "
                                f"not from {source} to {target}")
        except RateError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"  {sheet.money(minor, source)} -> "
                  f"{sheet.money(converted, target)}")
            print(f"  {sheet.fresh(on, args.limit)}")
        return 0

    try:
        amounts = read_amounts(args.amounts)
    except RateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {sheet.quote.base} on {sheet.quote.as_of.isoformat()}: "
              f"{len(sheet)} rate(s)")
        for line in sheet.quote.lines():
            print(f"    {line}")
        print(f"  {sheet.fresh(on, args.limit)}")
        print()
        for amount, code in amounts:
            converted = sheet.convert(amount, code)
            back = sheet.convert_back(converted, code)
            print(f"    {sheet.money(amount, sheet.quote.base):>14} -> "
                  f"{sheet.money(converted, code):>14} -> "
                  f"{sheet.money(back, sheet.quote.base):>14}"
                  f"   drift {back - amount:+d}")
        rates = legacy_table(sheet)
        print(f"  the legacy conversion of the same money: "
              f"100.00 USD -> {legacy_convert(100.00, rates['EUR']):.2f} EUR "
              f"-> {legacy_convert(legacy_convert(100.00, rates['EUR']), rates['EUR']):.2f} USD")

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        checks = audit(sheet, on, args.limit)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "as_of": sheet.quote.as_of.isoformat(),
            "base": sheet.quote.base,
            "read_on": on.isoformat(),
            "age_days": sheet.quote.age_days(on),
            "stale": sheet.quote.is_stale(on, args.limit),
            "rates": [
                {
                    "pair": rate.pair(),
                    "numerator": rate.numerator,
                    "denominator": rate.denominator,
                    "decimal": rate.decimal_text(),
                    "inverse": rate.inverse().text(),
                }
                for rate in sheet.quote.rates
            ],
            "exponents": {code: exponent
                          for code, exponent in sheet.exponents},
            "conversions": [
                {
                    "from": sheet.money(amount, sheet.quote.base),
                    "to": sheet.money(sheet.convert(amount, code), code),
                    "back": sheet.money(sheet.convert_back(
                        sheet.convert(amount, code), code), sheet.quote.base),
                    "drift": sheet.drift(amount, code),
                    "legacy_to": legacy_convert(
                        amount / 100, legacy_table(sheet)[code]),
                    "legacy_back": legacy_convert(
                        legacy_convert(amount / 100,
                                       legacy_table(sheet)[code]),
                        legacy_table(sheet)[code]),
                }
                for amount, code in amounts
            ],
            "unknown_currency": {
                "code": "CHF",
                "legacy_rate": legacy_rate(legacy_table(sheet), "CHF"),
            },
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
