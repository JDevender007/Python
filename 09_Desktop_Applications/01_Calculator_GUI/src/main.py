"""Command line front end for the calculator lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from calculator import (                                    # noqa: E402
    PLACES,
    CalcError,
    audit,
    compare,
    divide_half_up,
    evaluate,
    exact,
    legacy_calculate,
    parse_expressions,
    problems,
    read_expressions,
    render,
    run_demo,
    tokenize,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calculator-lab",
        description="Evaluate expressions exactly, and compare with eval.")
    parser.add_argument("--expressions", default=None, metavar="PATH",
                        help="a bundle of expressions (default: the bundled one)")
    parser.add_argument("--expression", default=None, metavar="TEXT",
                        help="evaluate one expression instead of the bundle")
    parser.add_argument("--places", default=PLACES, type=int, metavar="N",
                        help=f"decimal places to show (default: {PLACES}, 0-12)")
    parser.add_argument("--tokens", action="store_true",
                        help="print the tokens of each expression")
    parser.add_argument("--legacy", action="store_true",
                        help="print what eval says beside each answer")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the results to PATH as JSON")
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

    try:
        if args.expression is not None:
            expressions = parse_expressions(args.expression)
        else:
            expressions = read_expressions(args.expressions)
        if args.places < 0 or args.places > 12:
            raise CalcError(f"places is between 0 and 12, got {args.places}")
        results = compare(expressions, args.places)
    except CalcError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        for result in results:
            if args.tokens:
                try:
                    for token in tokenize(result.expression):
                        print(f"  {token.line()}")
                except CalcError as error:
                    print(f"  {result.expression}: {error}")
                    continue
            if args.legacy:
                print(f"  {result.line()}")
            else:
                print(f"  {result.expression:<20} {result.shown}")

    refusals = [(result.expression, result.shown) for result in results
                if result.shown.startswith("refused:")]
    checks = []
    failed: list[str] = []
    if args.audit:
        checks = audit(results, refusals)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "places": args.places,
            "results": [
                {
                    "expression": result.expression,
                    "legacy": result.legacy,
                    "shown": result.shown,
                    "differs": result.differs(),
                }
                for result in results
            ],
            "refusals": [{"expression": expression, "note": note}
                         for expression, note in refusals],
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
            "cross_check": {
                "divide_half_up_2675_1000": divide_half_up(2675, 1000, 2),
                "decimal_2_675": render(Decimal("2.675"), 2),
                "float_round_2_675": round(2.675, 2),
                "power_two_cubed": render(evaluate("2 ^ 3"), 0),
                "legacy_two_caret_three": legacy_calculate("2 ^ 3"),
                "third_exact": exact(evaluate("1/3")),
            },
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the results to {destination}")

    if failed:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
