"""Command line entry point for the journal.

Usage
-----
    python src/main.py --demo                       # self-checking demo
    python src/main.py                              # the bundled journal
    python src/main.py --search shelf
    python src/main.py --tag workshop
    python src/main.py --from 2024-03-05 --to 2024-03-15
    python src/main.py --stats
    python src/main.py --add "Title" --date 2024-04-01 --body "..." --tags diy
    python src/main.py --legacy                     # the two original bugs

``--add`` and ``--search`` operate on ``--file``, which defaults to the bundled
journal in read-only spirit: the file is only rewritten when ``--add`` is used
without ``--dry-run``.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import json
import sys
from pathlib import Path

from journal import (
    DATA_FILE,
    LEGACY_ALIGNED,
    LEGACY_RUNNABLE,
    LEGACY_SOURCE,
    JournalError,
    add,
    between,
    by_tag,
    load,
    render,
    run_demo,
    save,
    search,
    stats,
    tag_counts,
)

BANNER = """
====================================
 JOURNAL MANAGER
   dated entries, JSON Lines, search
====================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A dated journal stored as JSON Lines (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--legacy", action="store_true",
                        help="show the two syntax errors and the logic bug")
    parser.add_argument("--file", type=Path, default=None,
                        help=f"journal file (default: bundled {DATA_FILE.name})")
    parser.add_argument("--search", metavar="TERM", default=None,
                        help="case-insensitive search over titles, bodies, tags")
    parser.add_argument("--tag", metavar="TAG", default=None,
                        help="entries carrying one tag")
    parser.add_argument("--from", dest="start", metavar="DATE", default=None,
                        help="start of an inclusive date range (YYYY-MM-DD)")
    parser.add_argument("--to", dest="end", metavar="DATE", default=None,
                        help="end of an inclusive date range (YYYY-MM-DD)")
    parser.add_argument("--stats", action="store_true",
                        help="counts instead of entries")
    parser.add_argument("--tags", action="store_true",
                        help="tag usage instead of entries")
    parser.add_argument("--add", metavar="TITLE", default=None,
                        help="append one entry")
    parser.add_argument("--date", metavar="DATE", default=None,
                        help="date for --add (default: today)")
    parser.add_argument("--body", metavar="TEXT", default="",
                        help="body for --add")
    parser.add_argument("--add-tags", metavar="TAGS", default="",
                        help="comma or space separated tags for --add")
    parser.add_argument("--dry-run", action="store_true",
                        help="with --add, show the entry without writing")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the result as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def render_tags(counts: dict[str, int]) -> str:
    if not counts:
        return "  (no tags)"
    width = max(len(tag) for tag in counts)
    return "\n".join(f"  {tag:<{width}}  {count:>3}"
                     for tag, count in counts.items())


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
        except JournalError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    if args.legacy:
        try:
            compile(LEGACY_SOURCE, "<legacy journal>", "exec")
        except SyntaxError as exc:
            first = str(exc)
        else:                                            # pragma: no cover
            first = ""
        try:
            compile(LEGACY_ALIGNED, "<legacy journal>", "exec")
        except SyntaxError as exc:
            second = str(exc)
        else:                                            # pragma: no cover
            second = ""
        try:
            compile(LEGACY_RUNNABLE, "<legacy journal>", "exec")
        except SyntaxError as exc:                       # pragma: no cover
            third = str(exc)
        else:
            third = ""
        payload = {"mode": "legacy", "verbatim_error": first,
                   "aligned_error": second, "runnable_compiles": not third}
        if not args.quiet:
            print(BANNER)
            print(f"  verbatim       {first}")
            print(f"  else aligned   {second}")
            print(f"  break removed  compiles: {payload['runnable_compiles']}")
            print("  and the search still appended 'No entries found' after "
                  "every query")
        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0

    path = args.file or DATA_FILE
    try:
        entries = load(path)

        if args.add is not None:
            date = args.date or datetime.date.today().strftime("%Y-%m-%d")
            entry = add(entries, date, args.add, args.body, args.add_tags)[-1]
            if not args.dry_run:
                save(path, add(entries, date, args.add, args.body,
                               args.add_tags))
            payload = {"mode": "add", "entry": entry.to_dict(),
                       "written": not args.dry_run}
        elif args.search is not None:
            matches = search(entries, args.search)
            payload = {"mode": "search", "term": args.search,
                       "count": len(matches),
                       "entries": [entry.to_dict() for entry in matches]}
        elif args.tag is not None:
            matches = by_tag(entries, args.tag)
            payload = {"mode": "tag", "tag": args.tag, "count": len(matches),
                       "entries": [entry.to_dict() for entry in matches]}
        elif args.start is not None or args.end is not None:
            start = args.start or "1970-01-01"
            end = args.end or "9999-12-31"
            matches = between(entries, start, end)
            payload = {"mode": "range", "start": start, "end": end,
                       "count": len(matches),
                       "entries": [entry.to_dict() for entry in matches]}
        elif args.tags:
            counts = tag_counts(entries)
            payload = {"mode": "tags", "tags": counts}
        elif args.stats:
            payload = {"mode": "stats", "stats": stats(entries)}
        else:
            payload = {"mode": "list", "count": len(entries),
                       "entries": [entry.to_dict() for entry in entries]}
    except JournalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        if payload["mode"] == "add":
            print("  " + render_entry_text(payload["entry"]))
            print(f"\n  {'written to' if payload['written'] else 'not written, dry run:'}"
                  f" {path}")
        elif payload["mode"] == "tags":
            print(render_tags(payload["tags"]))
        elif payload["mode"] == "stats":
            for key, value in payload["stats"].items():
                print(f"  {key:<10} {value}")
        elif payload["mode"] in ("search", "tag", "range"):
            print(_render_dicts(payload["entries"]))
            count = payload["count"]
            print(f"\n  {count} match{'es' if count != 1 else ''}")
        else:
            print(_render_dicts(payload["entries"]))
            count = payload["count"]
            print(f"\n  {count} {'entry' if count == 1 else 'entries'}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {args.json}")
    return 0


def render_entry_text(raw: dict) -> str:
    tags = f"  [{' '.join(raw['tags'])}]" if raw["tags"] else ""
    lines = [f"#{raw['id']:<3} {raw['date']}  {raw['title']}{tags}"]
    if raw["body"]:
        lines.append(f"     {raw['body']}")
    return "\n".join(lines)


def _render_dicts(raws: list[dict]) -> str:
    if not raws:
        return "  (no entries)"
    return "\n\n".join(render_entry_text(raw) for raw in raws)


if __name__ == "__main__":
    raise SystemExit(main())
