"""Command line interface for the URL parser.

    python src/main.py --demo
    python src/main.py                       # the bundled 20 URLs
    python src/main.py --parse "https://user@example.com:8080/a?b=1#c"
    python src/main.py --normalise "HTTPS://Example.COM:443"
    python src/main.py --params "https://example.com/?q=a%20b&q=c"
    python src/main.py --legacy "https://www.kaggle.com/datasets"
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from urlkit import (
    DATA_FILE,
    URL,
    URLParseError,
    host_kind,
    legacy_parts,
    load_urls,
    normalise,
    parse,
    query_params,
    run_demo,
)

BANNER = """
====================================
 URL PARSING
   scheme, host, port, path, query
====================================
"""


def _render(url: URL) -> list[str]:
    return [
        f"  scheme     {url.scheme if url.scheme is not None else '(none)'}",
        f"  userinfo   {url.userinfo if url.userinfo is not None else '(none)'}",
        f"  host       {url.host or '(none)'} "
        f"({host_kind(url.host)})",
        f"  port       {url.port if url.port is not None else '(default)'}",
        f"  path       {url.path or '(empty)'}",
        f"  query      {url.query or '(empty)'}",
        f"  fragment   {url.fragment or '(empty)'}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse, normalise and inspect URLs.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="URL list (default: data/urls.txt)")
    parser.add_argument("--parse", metavar="URL",
                        help="show the components of one URL")
    parser.add_argument("--normalise", metavar="URL",
                        help="lowercase, drop the default port, fill the path")
    parser.add_argument("--params", metavar="URL",
                        help="decoded query parameters, repeats preserved")
    parser.add_argument("--legacy", metavar="URL",
                        help="show what the original find() slices produced")
    parser.add_argument("--json", type=Path, metavar="PATH",
                        help="write the result as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="write no standard output")
    args = parser.parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo()
        else:
            run_demo()
        return 0

    try:
        payload: dict = {}

        if args.parse is not None:
            url = parse(args.parse)
            payload = {"mode": "parse", "url": args.parse,
                       "components": url.to_dict(),
                       "host_kind": host_kind(url.host),
                       "rebuilt": url.to_url()}
            if not args.quiet:
                print(BANNER)
                print("\n".join(_render(url)))
        elif args.normalise is not None:
            normalised = normalise(args.normalise)
            payload = {"mode": "normalise", "url": args.normalise,
                       "normalised": normalised,
                       "changed": normalised != args.normalise}
            if not args.quiet:
                print(BANNER)
                print(f"  before  {args.normalise}")
                print(f"  after   {normalised}")
                if normalised == args.normalise:
                    print("  (already normalised)")
        elif args.params is not None:
            url = parse(args.params)
            pairs = query_params(url)
            payload = {"mode": "params", "url": args.params,
                       "count": len(pairs),
                       "params": [{"key": key, "value": value}
                                  for key, value in pairs]}
            if not args.quiet:
                print(BANNER)
                if pairs:
                    for key, value in pairs:
                        print(f"  {key} = {value}")
                else:
                    print("  (no query parameters)")
                print(f"\n  {len(pairs)} parameter(s)")
        elif args.legacy is not None:
            parts = legacy_parts(args.legacy)
            fixed = parse(args.legacy)
            payload = {"mode": "legacy", "url": args.legacy,
                       "protocol": parts["protocol"],
                       "domain": parts["domain"], "page": parts["page"],
                       "actual_host": fixed.host,
                       "actual_path": fixed.path}
            if not args.quiet:
                print(BANNER)
                print(f"  legacy protocol  {parts['protocol']!r}")
                print(f"  legacy domain    {parts['domain']!r}")
                print(f"  legacy page      {parts['page']!r}")
                print(f"\n  actual host      {fixed.host!r}")
                print(f"  actual path      {fixed.path!r}")
                if parts["domain"] != fixed.host:
                    print("  note: the legacy domain is not the host")
        else:
            urls = load_urls(args.file)
            payload = {"mode": "list", "file": args.file.name,
                       "count": len(urls),
                       "urls": [{"url": raw,
                                 "host": parse(raw).host,
                                 "kind": host_kind(parse(raw).host),
                                 "path": parse(raw).path}
                                for raw in urls]}
            if not args.quiet:
                print(BANNER)
                for raw in urls:
                    parsed = parse(raw)
                    print(f"  {parsed.host or '(no host)':<28.28} "
                          f"{host_kind(parsed.host):<12.12} "
                          f"{parsed.path or '/'}")
                print(f"\n  {len(urls)} URL(s)")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except URLParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
