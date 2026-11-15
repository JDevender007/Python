"""Command line for Duplicate_File_Finder.

    python src/main.py --demo
    python src/main.py
    python src/main.py --duplicates
    python src/main.py --verify
    python src/main.py --report out.csv
    python src/main.py --legacy
    python src/main.py --json out.json
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import finder
from finder import FindError, LegacyFinder, scan


def _human(size: int) -> str:
    """Bytes as a short human string, for the one-line summary."""
    if size < 1024:
        return f"{size} B"
    scaled = float(size)
    for unit in ("KB", "MB", "GB"):
        scaled = scaled / 1024
        if scaled < 1024:
            return f"{scaled:.1f} {unit}"
    return f"{scaled:.1f} TB"


def _show_groups(result) -> None:
    for index, group in enumerate(result.groups, start=1):
        print(f"  group {index}: {group.size} bytes each, "
              f"{len(group.copies)} copies, {group.reclaimable} reclaimable")
        for path in group.copies:
            print(f"    {path.name}")
    if not result.groups:
        print("  no duplicate groups: every file holds different bytes")


def _summary(result) -> None:
    summary = result.summary()
    print(f"  folder       {result.root}")
    print(f"  paths        {summary['paths']}")
    print(f"  files        {summary['files']} physical file(s)")
    print(f"  aliases      {summary['aliases']} second name(s) for a file")
    print(f"  groups       {summary['groups']} duplicate group(s)")
    print(f"  deletable    {summary['duplicate_files']} copy(ies)")
    print(f"  bytes        {summary['bytes']}")
    print(f"  reclaimable  {summary['reclaimable']} bytes "
          f"({_human(summary['reclaimable'])})")


def _legacy(folder) -> int:
    """What the legacy project reported, and what it got wrong."""
    paths = sorted(Path(folder).glob("*"))
    legacy = LegacyFinder()
    first = {content: list(members)
             for content, members in legacy.scan_files(paths).items()}
    print("  the legacy finder, one scan:")
    for content, members in first.items():
        print(f"    {content[:12]}  {len(members)} duplicate(s): "
              f"{', '.join(Path(member).name for member in members)}")
    print(f"  implied reclaimable: {legacy.reclaimable} bytes")

    skipped = [path.name for path in paths if path.stat().st_size == 0]
    print(f"  empty files it never looked at: "
          f"{', '.join(skipped) if skipped else 'none'}")

    again = legacy.scan_files(paths)
    print(f"  the same finder called a second time: "
          f"{sum(len(members) for members in again.values())} duplicate(s) "
          f"for {len(paths)} path(s)")
    print(f"  implied reclaimable: {legacy.reclaimable} bytes")

    honest = scan(folder)
    print(f"  this module: {honest.duplicate_files} deletable copy(ies) and "
          f"{honest.reclaimable} reclaimable bytes")
    print(f"  the skip it used was {finder.LEGACY_SKIP!r}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duplicate-finder",
        description="Find files whose bytes are identical, and tell a copy "
                    "from a second name for the same file.")
    parser.add_argument("--folder", default=None,
                        help="the folder to scan (default: the bundled data)")
    parser.add_argument("--duplicates", action="store_true",
                        help="list every duplicate group and its copies")
    parser.add_argument("--summary", action="store_true",
                        help="the counts and the reclaimable bytes")
    parser.add_argument("--verify", action="store_true",
                        help="re-read every group and prove its copies agree")
    parser.add_argument("--report", default=None, metavar="PATH",
                        help="write the groups as CSV to PATH")
    parser.add_argument("--legacy", action="store_true",
                        help="show what the legacy project reported")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the whole scan as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if not args.quiet:
            return finder.run_demo()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            return finder.run_demo()

    folder = Path(args.folder) if args.folder else finder.DATA_DIR

    try:
        if args.legacy:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    return _legacy(folder)
            return _legacy(folder)

        result = scan(folder)

        if args.verify:
            checks = result.verify()
            passed = sum(1 for _, ok in checks if ok)
            if not args.quiet:
                for name, ok in checks:
                    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
                print(f"\n  {passed}/{len(checks)} checks passed")
            return 0 if passed == len(checks) else 1

        if args.report:
            target = Path(args.report)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(finder.report_text(result), encoding="utf-8")
            if not args.quiet:
                rows = len(result.groups)
                print(f"  wrote {rows} group(s) to {target}")
            return 0

        if args.json:
            target = Path(args.json)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result.to_dict(), indent=2) + "\n",
                              encoding="utf-8")
            if not args.quiet:
                print(f"  wrote the scan of {len(result)} path(s) to {target}")
            return 0

        if args.quiet:
            return 0

        if args.duplicates:
            _show_groups(result)
        elif args.summary:
            _summary(result)
        else:
            _summary(result)
            print()
            _show_groups(result)
        return 0
    except FindError as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
