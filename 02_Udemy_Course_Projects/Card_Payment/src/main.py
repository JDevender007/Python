"""Command line entry point for the card toolkit.

Usage
-----
    python src/main.py --demo                       # self-checking demo
    python src/main.py                              # bundled cards, masked
    python src/main.py --check 4111111111111111     # one verdict
    python src/main.py --mask 378282246310005       # safe display only
    python src/main.py --generate 4111 16           # a valid test number
    python src/main.py --file cards.csv --json out.json --quiet

Every mode prints masked numbers only. The full digits are used for the maths
and then discarded, which is the whole point of the project.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from card import (
    DATA_FILE,
    CardError,
    check,
    describe,
    digits,
    format_number,
    generate,
    load_cards,
    luhn_sum,
    mask,
    run_demo,
)

BANNER = """
====================================
 CARD PAYMENT
   Luhn, brand, length, masked view
====================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and safely display card numbers (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=None,
                        help=f"card file (default: {DATA_FILE.name})")
    parser.add_argument("--check", metavar="NUMBER", default=None,
                        help="validate one number and explain the verdict")
    parser.add_argument("--mask", metavar="NUMBER", default=None,
                        help="masked display and nothing else")
    parser.add_argument("--generate", nargs=2, metavar=("PREFIX", "LENGTH"),
                        default=None,
                        help="build a deterministic Luhn-valid test number")
    parser.add_argument("--reveal", type=int, default=4,
                        help="trailing digits to show (0-6, default 4)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the result as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def render_table(records: list[dict]) -> str:
    lines = [f"  {'masked':<25}{'brand':<12}{'len':<5}{'luhn':<6}verdict",
             "  " + "-" * 59]
    for record in records:
        verdict = "valid" if record["valid"] else "invalid"
        lines.append(f"  {record['masked']:<25}{record['brand']:<12}"
                     f"{record['length']:<5}"
                     f"{'yes' if record['luhn'] else 'no':<6}{verdict}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except CardError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        if args.generate is not None:
            prefix, length = args.generate
            number = generate(prefix, int(length))
            info = check(number)
            payload = {"mode": "generate", "number": number,
                       "digits": info["digits"], "brand": info["brand"],
                       "length": info["length"], "luhn": info["luhn"],
                       "valid": info["valid"], "masked": info["masked"]}
        elif args.mask is not None:
            payload = {"mode": "mask", "masked": mask(args.mask, args.reveal),
                       "length": len(digits(args.mask))}
        elif args.check is not None:
            info = check(args.check)
            payload = {"mode": "check", **info,
                       "description": describe(args.check),
                       "luhn_sum": luhn_sum(info["digits"])}
        else:
            records = load_cards(args.file or DATA_FILE)
            for record in records:
                record["masked"] = mask(record["digits"], args.reveal)
            payload = {
                "mode": "list",
                "cards": records,
                "count": len(records),
                "valid": sum(1 for record in records if record["valid"]),
                "invalid": sum(1 for record in records if not record["valid"]),
                "reveal": args.reveal,
            }
    except CardError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        if payload["mode"] == "generate":
            print(f"  generated {payload['number']}")
            print(f"  formatted {format_number(payload['digits'])}")
            print(f"  {payload['brand']}, {payload['length']} digits, "
                  f"Luhn {'yes' if payload['luhn'] else 'no'}")
            print(f"  masked    {payload['masked']}")
        elif payload["mode"] == "mask":
            print(f"  {payload['masked']}")
            print(f"  {payload['length']} digit(s), last "
                  f"{min(args.reveal, payload['length'])} shown")
        elif payload["mode"] == "check":
            print(f"  {payload['description']}")
            print(f"  formatted  {payload['formatted']}")
            print(f"  length     {payload['length']} "
                  f"({'allowed' if payload['length_ok'] else 'not allowed'})")
            print(f"  luhn sum   {payload['luhn_sum']} "
                  f"({'multiple of 10' if payload['luhn'] else 'not a multiple of 10'})")
        else:
            print(render_table(payload["cards"]))
            print(f"\n  {payload['count']} card(s): "
                  f"{payload['valid']} valid, {payload['invalid']} rejected")
            if payload["reveal"] != 4:
                print(f"  showing the last {payload['reveal']} digit(s)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
