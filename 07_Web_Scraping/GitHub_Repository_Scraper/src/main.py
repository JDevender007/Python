"""Command line front end for the count lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from counts import (                                        # noqa: E402
    CountError,
    audit,
    format_gain,
    gain,
    legacy_clean_number,
    legacy_magnitude,
    parse_count,
    problems,
    read_history,
    read_listing,
    relation,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="count-lab",
        description="Read a displayed count with the step it was printed in, "
                    "and never claim two figures the page could not tell "
                    "apart are different.")
    parser.add_argument("--listing", default=None, metavar="PATH",
                        help="a repository page to read (default: the "
                             "bundled one)")
    parser.add_argument("--history", default=None, metavar="PATH",
                        help="a tick<TAB>count log (default: the bundled one)")
    parser.add_argument("--count", default=None, metavar="TEXT",
                        help="read one count and print its amount and step")
    parser.add_argument("--compare", nargs=2, default=None, metavar=("A", "B"),
                        help="compare two displayed counts")
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

    if args.count is not None:
        try:
            count = parse_count(args.count)
        except CountError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"  {args.count!r} is {count.format()} = "
                  f"{count.amount:,} items")
            print(f"  printed in steps of {count.resolution:,}, so anywhere "
                  f"between {count.low():,} and {count.high():,}")
            if count.exact:
                print("  every digit was printed, so the figure is exact")
            print(f"  the legacy cleaner would have said "
                  f"{legacy_clean_number(args.count):,}, and the legacy "
                  f"magnitude reader {legacy_magnitude(args.count):,}")
        return 0

    if args.compare is not None:
        try:
            left = parse_count(args.compare[0])
            right = parse_count(args.compare[1])
        except CountError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            verdict = relation(left, right)
            print(f"  {left.format()} is {verdict} {right.format()}")
            if verdict == "indistinguishable":
                print(f"  {left.format()} covers {left.low():,}.."
                      f"{left.high():,} and {right.format()} covers "
                      f"{right.low():,}..{right.high():,}: the page never "
                      f"printed enough digits to separate them")
            print(f"  the second is {format_gain(gain(left, right))} from "
                  f"the first, at worst and at best")
        return 0

    try:
        listing = read_listing(args.listing)
        history = read_history(args.history)
    except CountError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {len(listing)} repositories on the page:")
        for repo in listing.repos:
            print(f"    {repo.line()}")
        print()
        for repo in listing.repos:
            print(f"    {repo.star_line()}")

        print(f"\n  the star count over {len(history)} days:")
        for line in history.lines():
            print(f"    {line}")
        low, high = history.gained()
        print(f"  gained from the first sample to the last: "
              f"{format_gain((low, high))}")

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        checks = audit(listing, history)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "listing": [
                {
                    "name": repo.name,
                    "stars": None if repo.stars is None else {
                        "text": repo.stars.format(),
                        "amount": repo.stars.amount,
                        "step": repo.stars.resolution,
                        "low": repo.stars.low(),
                        "high": repo.stars.high(),
                    },
                    "forks": None if repo.forks is None else
                    repo.forks.amount,
                    "language": repo.language,
                    "note": repo.note,
                }
                for repo in listing.repos
            ],
            "history": [
                {"at": sample.at, "amount": sample.count.amount,
                 "step": sample.count.resolution}
                for sample in history.samples
            ],
            "gained": list(history.gained()),
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
