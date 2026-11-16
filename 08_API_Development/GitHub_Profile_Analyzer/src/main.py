"""Command line front end for the page lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pagination import (                                    # noqa: E402
    MAX_PAGES,
    PER_PAGE,
    Item,
    PageError,
    Repository,
    audit,
    cursor_walk,
    is_repository_row,
    legacy_fetch,
    offset_walk,
    problems,
    read_repositories,
    run_demo,
    row_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="page-lab",
        description="Walk a paginated collection by page number and by "
                    "cursor, and see which one duplicates a row when the list "
                    "moves.")
    parser.add_argument("--repos", default=None, metavar="PATH",
                        help="a repository list (default: the bundled one)")
    parser.add_argument("--per-page", default=PER_PAGE, type=int,
                        metavar="N", help=f"items per page (default: {PER_PAGE})")
    parser.add_argument("--walk", default=None, choices=("offset", "cursor"),
                        help="walk one way and print every page")
    parser.add_argument("--insert", action="store_true",
                        help="push the arriving repository after page 1, as the "
                             "demo does")
    parser.add_argument("--error-page", default=None, type=int, metavar="N",
                        help="answer page N with a rate-limit envelope, for the "
                             "legacy loop")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict; the checks "
                             "describe a walk while one repository arrives, so "
                             "an arrival is applied")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the walks to PATH as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def _server(items, arriving, error_page):
    server = Repository(items, arriving)
    server.error_on = error_page
    return server


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        items, arriving = read_repositories(args.repos)
    except PageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if arriving is None:
        print("error: the bundle names no arriving repository", file=sys.stderr)
        return 2

    if args.per_page < 1 or args.per_page > 100:
        print(f"error: a page size is between 1 and 100, got {args.per_page}",
              file=sys.stderr)
        return 2

    moving = args.insert or args.audit

    def pusher(page):
        if moving and page.number == 1:
            server.arrive()

    # -- one walk, printed -------------------------------------------------- #
    if args.walk is not None:
        server = _server(items, arriving, args.error_page)
        try:
            if args.walk == "offset":
                walk = offset_walk(server, args.per_page, pusher)
            else:
                walk = cursor_walk(server, args.per_page, pusher)
        except PageError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            for page in walk.pages:
                print(f"  [{', '.join(item.name for item in page)}]")
            print(f"  {walk.line()}")
            if walk.duplicates():
                print(f"  duplicated: "
                      f"{', '.join(item.name for item in walk.duplicates())}")
            stranded = walk.missing(items + (arriving,))
            if stranded:
                print(f"  never seen: "
                      f"{', '.join(item.name for item in stranded)}")
        return 0

    # -- both walks, compared ----------------------------------------------- #
    server = _server(items, arriving, args.error_page)
    offset = offset_walk(server, args.per_page, pusher)
    server = _server(items, arriving, args.error_page)
    cursor = cursor_walk(server, args.per_page, pusher)
    server = _server(items, arriving, args.error_page)

    def legacy_pusher(number):
        if moving and number == 1:
            server.arrive()

    legacy = legacy_fetch(server, args.per_page, legacy_pusher)
    server = _server(items, arriving, args.error_page or 2)
    legacy_error = legacy_fetch(server, args.per_page)

    if not args.quiet:
        print(f"  {len(items)} repositories, page size {args.per_page}")
        print(f"  {offset.line()}")
        print(f"  {cursor.line()}")
        junk = [row for row in legacy_error if not is_repository_row(row)]
        print(f"  legacy: {len(legacy)} row(s), "
              f"{len([row for row in legacy if is_repository_row(row)])} "
              f"repositories")
        print(f"  legacy with a {'403' if junk else 'plain'} page 2: "
              f"{len(legacy_error)} row(s), {len(junk)} of them keys: "
              f"{', '.join(junk)}")

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        checks = audit(offset, cursor, legacy, legacy_error, items, arriving,
                       args.per_page)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)

        def walk_json(walk):
            return {
                "mode": walk.mode,
                "stopped": walk.stopped,
                "pages": [
                    {
                        "number": number,
                        "names": [item.name for item in page],
                        "ids": [item.id for item in page],
                    }
                    for number, page in enumerate(walk.pages, start=1)
                ],
                "totals": list(walk.totals),
                "rows": len(walk.rows()),
                "unique": len(walk.unique()),
                "duplicates": [item.name for item in walk.duplicates()],
                "missing": [item.name
                            for item in walk.missing(items + (arriving,))],
                "shortfall": walk.shortfall(),
            }

        payload = {
            "repositories": [str(item) for item in items],
            "arriving": str(arriving),
            "per_page": args.per_page,
            "offset": walk_json(offset),
            "cursor": walk_json(cursor),
            "legacy": {
                "rows": len(legacy),
                "repositories": len([row for row in legacy
                                     if is_repository_row(row)]),
                "error_rows": [row for row in legacy_error
                               if not is_repository_row(row)],
            },
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the walks to {destination}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
