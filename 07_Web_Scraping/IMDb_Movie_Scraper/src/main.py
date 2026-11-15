"""Command line front end for the runtime lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from durations import (                                     # noqa: E402
    BUDGET_MINUTES,
    Duration,
    DurationError,
    audit,
    legacy_minutes,
    parse_duration,
    plan,
    problems,
    read_catalogue,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runtime-lab",
        description="Read a runtime as whole minutes in one unit, keep an "
                    "unknown runtime unknown, and plan a marathon that never "
                    "overspends its budget.")
    parser.add_argument("--page", default=None, metavar="PATH",
                        help="a title page to read (default: the bundled one)")
    parser.add_argument("--runtime", default=None, metavar="TEXT",
                        help="read one runtime and print its minutes")
    parser.add_argument("--budget", default=None, metavar="TEXT",
                        help="plan a marathon with this much time")
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

    if args.runtime is not None:
        try:
            runtime = parse_duration(args.runtime)
        except DurationError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"  {args.runtime!r} is {runtime.format()} = "
                  f"{runtime.minutes} minutes")
            print(f"  {runtime.hours} whole hour(s) and {runtime.rest} "
                  f"minute(s)")
            print(f"  the legacy reader would have said "
                  f"{legacy_minutes(args.runtime)}")
        return 0

    try:
        catalogue = read_catalogue(args.page)
    except DurationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    budget = Duration(BUDGET_MINUTES)
    if args.budget:
        try:
            budget = parse_duration(args.budget)
        except DurationError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2

    show = catalogue.series[0] if catalogue.series else None
    marathon = plan(catalogue.films, budget)

    if not args.quiet:
        print(f"  {len(catalogue.films)} film(s) on the page:")
        for film in catalogue.films:
            print(f"    {film.line()}")
        print()
        for film in catalogue.films:
            print(f"    {film.minutes_line()}")
        for series in catalogue.series:
            print(f"    {series.line()}")
            if series.total() is not None:
                print(f"    {'':<12} {series.total().minutes:,} minutes in "
                      f"total")
        print()
        print(f"  a marathon with {budget.format()} to spend: "
              f"{marathon.line()}")
        for film in marathon.films:
            print(f"    takes {film.title:<12} {film.runtime.format():>10}")

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        if show is None:
            print("error: the page holds no series to check", file=sys.stderr)
            return 2
        checks = audit(catalogue, show, marathon)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "films": [
                {
                    "title": film.title,
                    "runtime": None if film.runtime is None else
                    film.runtime.minutes,
                    "text": None if film.runtime is None else
                    film.runtime.format(),
                    "year": film.year,
                    "note": film.note,
                }
                for film in catalogue.films
            ],
            "series": [
                {
                    "title": series.title,
                    "per_episode": None if series.per_episode is None else
                    series.per_episode.minutes,
                    "episodes": series.episodes,
                    "total": None if series.total() is None else
                    series.total().minutes,
                }
                for series in catalogue.series
            ],
            "marathon": {
                "budget": marathon.budget.minutes,
                "films": list(marathon.titles()),
                "total": None if marathon.total() is None else
                marathon.total().minutes,
                "remaining": None if marathon.remaining() is None else
                marathon.remaining().minutes,
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
