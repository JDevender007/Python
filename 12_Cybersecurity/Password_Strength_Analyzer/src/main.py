"""Command line entry point for the Password Strength Analyzer.

Usage
-----
    python src/main.py --demo                      # analyse bundled sample passwords
    python src/main.py --password "correct horse"  # analyse one password
    python src/main.py --stdin                     # read password from stdin
    python src/main.py --password "x" --json       # machine-readable output

Passwords are processed in memory only: never stored, never transmitted.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from analyzer import analyze, mask, render_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("pwd_analyzer")

BANNER = """
========================================
 PASSWORD STRENGTH ANALYZER
   local only - nothing is stored
========================================
"""

# Obviously fake samples used by the demo (never real credentials).
DEMO_SAMPLES = [
    "password",
    "123456",
    "Sunshine1",
    "Tr0ub4dor&3",
    "correct-horse-battery-staple",
    "G7$zqL!vNn2@wQe",
]


def run_demo() -> int:
    """Analyse the bundled sample set and print a report for each."""
    print(BANNER)
    for sample in DEMO_SAMPLES:
        report = analyze(sample)
        print("-" * 56)
        print(render_report(report, password=sample))
        print()
    print("Demo completed successfully.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local password strength analyser")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--password", help="password to analyse (prefer --stdin)")
    source.add_argument("--stdin", action="store_true", help="read the password from stdin")
    source.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--rate", type=float, default=None,
                        help="override offline attack rate (guesses/second)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if args.password is not None:
        password = args.password
    elif args.stdin:
        password = sys.stdin.read().rstrip("\n")
    else:
        parser.error("provide --password, --stdin, or --demo")

    if not password:
        print("Error: password must not be empty", file=sys.stderr)
        return 2

    rates = None
    if args.rate is not None:
        if args.rate <= 0:
            print("Error: --rate must be positive", file=sys.stderr)
            return 2
        rates = {"custom": args.rate}

    try:
        report = analyze(password, rates=rates)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(BANNER)
    if args.json:
        payload = report.to_dict()
        payload["password_masked"] = mask(password)
        print(json.dumps(payload, indent=2))
    else:
        print(render_report(report, password=password))

    # non-zero exit when the password is weak, so scripts can gate on it
    return 0 if report.score >= 40 else 3


if __name__ == "__main__":
    raise SystemExit(main())
