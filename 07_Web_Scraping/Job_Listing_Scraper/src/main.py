"""Command line front end for the link lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from urls import (                                          # noqa: E402
    BASE_URL,
    UrlError,
    audit,
    dedupe,
    legacy_join,
    legacy_valid,
    parse_url,
    problems,
    read_page,
    resolve,
    run_demo,
    same_site,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="link-lab",
        description="Resolve a link against the page it was printed on, keep "
                    "a crawl on one host by equality, and never fetch the "
                    "same page twice.")
    parser.add_argument("--links", default=None, metavar="PATH",
                        help="an href<TAB>label page (default: the bundled "
                             "one)")
    parser.add_argument("--base", default=BASE_URL, metavar="URL",
                        help="the address the page was printed at")
    parser.add_argument("--resolve", nargs="+", default=None, metavar="HREF",
                        help="resolve one or more hrefs against the base")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the crawl to PATH as JSON")
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
        base = parse_url(args.base)
    except UrlError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.resolve is not None:
        status = 0
        for href in args.resolve:
            try:
                url = resolve(base, href)
            except UrlError as error:
                print(f"error: {error}", file=sys.stderr)
                status = 2
                continue
            if not args.quiet:
                where = "on site" if same_site(url, base) else "OFF SITE"
                print(f"  {href!r} -> {url}  ({where})")
                print(f"    the legacy join would have made "
                      f"{legacy_join(str(base), href)!r}")
        return status

    try:
        page = read_page(args.links, args.base)
    except UrlError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {len(page.links)} anchor(s) on {page.base}")
        for link in page.links:
            print(f"    {link.line()}")
        print()
        print(f"  {len(page.refused())} refused, {len(page.offsite())} off "
              f"site, {len(page.urls())} on site, {len(page.crawl())} unique")
        for url in page.crawl():
            print(f"    {url}")
        print(f"  job ids: "
              f"{', '.join(str(url.job_id()) for url in page.jobs())}")

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        checks = audit(page)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "base": str(page.base),
            "links": [
                {
                    "href": link.href,
                    "label": link.label,
                    "url": None if link.url is None else str(link.url),
                    "note": link.note,
                    "legacy_valid": legacy_valid(
                        str(link.url) if link.url is not None else link.href),
                }
                for link in page.links
            ],
            "crawl": [str(url) for url in page.crawl()],
            "jobs": [{"id": url.job_id(), "url": str(url)}
                     for url in page.jobs()],
            "duplicates": len(page.urls()) - len(dedupe(page.urls())),
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the crawl to {destination}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
