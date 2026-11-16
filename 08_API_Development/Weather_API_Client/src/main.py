"""Command line front end for the units lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from observations import (                                  # noqa: E402
    ObservationError,
    audit,
    legacy_temperature,
    parse_blocks,
    plain_decode,
    problems,
    read_observation,
    read_table,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="units-lab",
        description="Read a weather response as a temperature with a unit, a "
                    "shape and a type, and never let a missing value look "
                    "like 0.0 degrees.")
    parser.add_argument("--readings", default=None, metavar="PATH",
                        help="a bundle of response bodies (default: the "
                             "bundled one)")
    parser.add_argument("--body", default=None, metavar="JSON",
                        help="read one body given on the command line")
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

    if args.body is not None:
        observation = read_observation("inline", args.body)
        if not args.quiet:
            print(f"  {observation.line()}")
            try:
                legacy = legacy_temperature(plain_decode(args.body))
            except json.JSONDecodeError:
                legacy = None
            if legacy is None:
                print("  the legacy reader never ran: the body is not JSON")
            else:
                print(f"  the legacy reader answers {legacy:.2f} C for it")
        if not observation.ok():
            print(f"error: {observation.note}", file=sys.stderr)
            return 2
        return 0

    try:
        table = read_table(args.readings)
    except ObservationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {len(table)} body(s): {len(table.readings())} reading(s), "
              f"{len(table.refusals())} refusal(s)")
        for line in table.lines():
            print(f"    {line}")

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        checks = audit(table)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "observations": [
                {
                    "station": item.station,
                    "celsius": None if item.temperature is None else
                    item.temperature.celsius_text(),
                    "kelvin": None if item.temperature is None else
                    item.temperature.text("kelvin"),
                    "fahrenheit": None if item.temperature is None else
                    item.temperature.text("fahrenheit"),
                    "hundredths": None if item.temperature is None else
                    item.temperature.hundredths,
                    "humidity": item.humidity,
                    "note": item.note,
                }
                for item in table.observations
            ],
            "readings": len(table.readings()),
            "refusals": len(table.refusals()),
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
