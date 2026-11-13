"""Command line entry point for the expression calculator.

Usage
-----
    python src/main.py --demo                    # self-checking demo
    python src/main.py                           # bundled expressions file
    python src/main.py --expr "2 + 3 * 4"        # one expression
    python src/main.py --expr "sqrt(16)" --expr "max(2, 7)"
    python src/main.py --file my.txt --json out.json
    python src/main.py --quiet --expr "1 + 1"

Everything is evaluated locally by ``calculator.evaluate``; nothing is read
from the network and no expression is ever handed to ``eval()``.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from calculator import (
    CalculatorError,
    evaluate_lines,
    format_value,
    run_demo,
)

BANNER = """
====================================
 CALCULATOR CLI
   tokenizer, shunting-yard, RPN
====================================
"""

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "expressions.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate arithmetic expressions with a hand-written "
                    "tokenizer and shunting-yard parser (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--expr", action="append", default=None,
                        metavar="EXPR",
                        help="expression to evaluate (repeatable)")
    parser.add_argument("--file", type=Path, default=None,
                        help="file of expressions, one per line "
                             "(default: data/expressions.txt)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the results as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def read_source(path: Path) -> list[str]:
    if not path.exists():
        raise CalculatorError(f"file not found: {path}")
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:                        # pragma: no cover - disk error
        raise CalculatorError(f"cannot read {path}: {exc}") from exc


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
        except CalculatorError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        if args.expr:
            source = args.expr
        else:
            source = read_source(args.file or DEFAULT_FILE)
        results, failures = evaluate_lines(source)
    except CalculatorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        for expression, value in results:
            print(f"  {expression:<26} = {format_value(value)}")
        for expression, message in failures:
            print(f"  {expression:<26} ! {message}")
        print(f"\n{len(results)} evaluated, {len(failures)} failed")

    if args.json:
        payload = {
            "results": [{"expression": text, "value": value}
                        for text, value in results],
            "failures": [{"expression": text, "error": message}
                         for text, message in failures],
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
