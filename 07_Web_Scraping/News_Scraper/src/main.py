"""Command line front end for the clock lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from timestamps import (                                    # noqa: E402
    READ_AT,
    TimeError,
    audit,
    legacy_age,
    legacy_fallback,
    parse_feed,
    parse_timestamp,
    problems,
    read_feed,
    reading_time,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clock-lab",
        description="Read a timestamp as an instant in UTC, resolve a relative "
                    "phrase against a supplied reading time, and never let an "
                    "unreadable date look new.")
    parser.add_argument("--feed", default=None, metavar="PATH",
                        help="an id/title/timestamp feed (default: the "
                             "bundled one)")
    parser.add_argument("--at", default=READ_AT, metavar="TEXT",
                        help=f"the moment the page is read (default: {READ_AT})")
    parser.add_argument("--timestamp", default=None, metavar="TEXT",
                        help="read one timestamp and print the instant")
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

    try:
        now = reading_time(args.at)
    except TimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.timestamp is not None:
        try:
            moment = parse_timestamp(args.timestamp, now)
        except TimeError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"  {args.timestamp!r} is {moment.iso()} "
                  f"({moment.human()})")
            print(f"  read at {now.iso()}, that is "
                  f"{moment.age_text(now)}")
            legacy = legacy_fallback(args.timestamp)
            print(f"  the legacy parser answers "
                  f"{legacy.strftime('%Y-%m-%d %H:%M:%S')} for it, "
                  f"unzoned and therefore 'now' whenever it could not read "
                  f"it")
        return 0

    try:
        feed = read_feed(args.feed, now)
    except TimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  read at {now.iso()}: {len(feed.articles)} article(s)")
        for line in feed.lines():
            print(f"    {line}")
        if feed.unknown():
            print()
            for article in feed.unknown():
                print(f"    {article.note_line()}")
        newest = feed.newest()
        if newest is not None:
            print()
            print(f"  newest by instant: {newest.id} at "
                  f"{newest.moment.iso()} ({newest.moment.age_text(now)})")
        by_text = sorted(feed.known(),
                         key=lambda article: article.printed)
        if by_text:
            print(f"  newest by text:    {by_text[-1].id} at "
                  f"{by_text[-1].printed!r}")

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        checks = audit(feed)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "read_at": now.iso(),
            "articles": [
                {
                    "id": article.id,
                    "title": article.title,
                    "printed": article.printed,
                    "moment": None if article.moment is None else
                    article.moment.iso(),
                    "age": None if article.moment is None else
                    article.moment.age_text(now),
                    "note": article.note,
                }
                for article in feed.articles
            ],
            "order": [article.id for article in feed.order()],
            "unknown": [article.id for article in feed.unknown()],
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
