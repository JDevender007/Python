"""Command line front end for the file lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from explorer import (                                      # noqa: E402
    KINDS,
    LISTING_FILE,
    UNITS,
    Entry,
    ExplorerError,
    audit,
    confine,
    contains,
    format_size,
    hidden,
    is_hidden,
    legacy_format_size,
    legacy_normalised,
    legacy_sort_entries,
    measure,
    natural_key,
    parse_listing,
    problems,
    read_listing,
    run_demo,
    sort_entries,
    sort_names,
    visible,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file-lab",
        description="List a folder by value, without case, and inside its root.")
    parser.add_argument("--listing", default=None, metavar="PATH",
                        help="a listing file (default: the bundled one)")
    parser.add_argument("--sort", default="natural",
                        choices=("natural", "legacy"),
                        help="how to order the names (default: natural)")
    parser.add_argument("--hidden", action="store_true",
                        help="include the hidden names")
    parser.add_argument("--resolve", default=None, metavar="NAME",
                        help="join a name to --root, or refuse it")
    parser.add_argument("--root", default="data/site", metavar="PATH",
                        help="the root --resolve is confined to "
                             "(default: data/site)")
    parser.add_argument("--size", default=None, type=int, metavar="BYTES",
                        help="print one size, here and from the legacy formatter")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the listing and the measurements to PATH")
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
        entries = read_listing(args.listing)
        resolved = None
        if args.resolve is not None:
            resolved = confine(args.root, args.resolve)
        if args.size is not None:
            format_size(args.size)
    except ExplorerError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    shown = visible(entries) if not args.hidden else sort_entries(entries)
    if args.sort == "legacy":
        ordered = legacy_sort_entries(entries)
        shown = tuple(entry for entry in ordered
                      if args.hidden or not entry.hidden())

    if not args.quiet:
        print(f"  {len(shown)} of {len(entries)} entr(ies), "
              f"{args.sort} order")
        for entry in shown:
            print(f"  {entry.line()}")
        if resolved is not None:
            print(f"  {args.root!r} + {args.resolve!r} -> {resolved}")
            print(f"  data/site-other/x.txt is "
                  f"{'inside' if contains(args.root, 'data/site-other/x.txt') else 'outside'} "
                  f"{args.root!r} here, and "
                  f"{'inside' if str('data/site-other/x.txt').startswith(args.root) else 'outside'} "
                  f"to startswith()")
        if args.size is not None:
            print(f"  {args.size} bytes -> {format_size(args.size)} here, "
                  f"{legacy_format_size(args.size)} from a float")

    checks = []
    failed: list[str] = []
    measured: dict = {}
    if args.audit:
        measured = measure(entries)
        checks = audit(measured, entries)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "order": args.sort,
            "root": args.root,
            "resolved": resolved,
            "entries": [
                {
                    "name": entry.name,
                    "kind": entry.kind,
                    "bytes": entry.size,
                    "size": entry.shown_size(),
                    "legacy_size": entry.legacy_size(),
                    "hidden": is_hidden(entry.name),
                    "key": [list(part) for part in natural_key(entry.name)],
                }
                for entry in shown
            ],
            "hidden": [entry.name for entry in hidden(entries)],
            "measurements": measured,
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the listing to {destination}")

    if failed:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
