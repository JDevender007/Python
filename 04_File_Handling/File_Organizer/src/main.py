"""Command line for File_Organizer.

    python src/main.py --demo
    python src/main.py                 # print the plan, move nothing
    python src/main.py --verify
    python src/main.py --legacy
    python src/main.py --categories
    python src/main.py --json plan.json
    python src/main.py --apply --inbox IN --out OUT
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

import organizer
from organizer import (CATEGORIES, INBOX, OUT, OrganizeError, apply_plan,
                       build_plan, classify, legacy_plan)


def _show_plan(plan) -> None:
    grouped = plan.by_category()
    if not grouped:
        print("  nothing to do: the inbox holds no loose files")
    for category, moves in grouped.items():
        print(f"  {category}  ({len(moves)} file(s))")
        for move in moves:
            marker = f"  (was {move.source.name})" if move.renamed else ""
            print(f"    {move.target.name:<24} {move.size:>7} bytes{marker}")
    if plan.folders:
        names = ", ".join(folder.name + "/" for folder in plan.folders)
        print(f"  skipped {len(plan.folders)} subfolder(s), which are not "
              f"loose files: {names}")


def _summary(plan) -> None:
    summary = plan.summary()
    print(f"  inbox        {plan.inbox}")
    print(f"  library      {plan.out_root}")
    print(f"  files        {summary['files']}")
    print(f"  moves        {summary['moves']} in {summary['categories']} "
          f"folder(s)")
    print(f"  renamed      {summary['renamed']}")
    print(f"  bytes        {summary['bytes']}")
    print(f"  subfolders   {summary['folders']} skipped")


def _legacy(inbox, out_root) -> int:
    plan = build_plan(inbox, out_root)
    legacy = dict(legacy_plan(inbox, out_root))
    print("  the legacy table, applied to every name in the inbox:")
    for name, target in legacy.items():
        ours = next(move for move in plan.moves if move.source.name == name)
        note = "" if target == f"{ours.category}/{ours.target.name}" else \
            f"   <- this module: {ours.category}/{ours.target.name}"
        print(f"    {name:<18} -> {target}{note}")
    misfiled = [name for name, target in legacy.items()
                if target.split("/")[0] !=
                next(move.category for move in plan.moves
                     if move.source.name == name)]
    print(f"  the legacy table misplaces {len(misfiled)} of {len(legacy)} "
          f"file(s): {', '.join(misfiled)}")
    print(f"  its suffix call is {organizer.LEGACY_SUFFIX!r}")
    print(f"  its counter line is {organizer.LEGACY_COUNTER!r}")
    return 0


def _categories() -> int:
    for category in CATEGORIES:
        if category in organizer.SINGLE:
            suffixes = " ".join(organizer.SINGLE[category])
            print(f"  {category:<10} {suffixes}")
        else:
            print(f"  {category:<10} (the fallback: no known suffix)")
    compounds = " ".join(sorted(organizer.COMPOUND, key=len, reverse=True))
    print(f"  {'compound':<10} {compounds}")
    print("  a suffix matches case-insensitively and the longest one wins, "
          "so backup.TAR.GZ is Archives by .tar.gz")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file-organizer",
        description="Plan every move from an inbox into an organised library, "
                    "and apply the plan only when asked.")
    parser.add_argument("--inbox", default=None,
                        help="the folder to read (default: the bundled inbox)")
    parser.add_argument("--out", default=None,
                        help="the library root (default: the bundled one)")
    parser.add_argument("--apply", action="store_true",
                        help="do the moves; without it nothing is touched")
    parser.add_argument("--verify", action="store_true",
                        help="run the seven plan checks")
    parser.add_argument("--legacy", action="store_true",
                        help="compare the legacy table with this module")
    parser.add_argument("--categories", action="store_true",
                        help="print the suffix table")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the plan as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if not args.quiet:
            return organizer.run_demo()
        with contextlib.redirect_stdout(io.StringIO()):
            return organizer.run_demo()

    inbox = Path(args.inbox) if args.inbox else INBOX
    out_root = Path(args.out) if args.out else OUT

    try:
        if args.categories:
            if not args.quiet:
                return _categories()
            with contextlib.redirect_stdout(io.StringIO()):
                return _categories()

        if args.legacy:
            if not args.quiet:
                return _legacy(inbox, out_root)
            with contextlib.redirect_stdout(io.StringIO()):
                return _legacy(inbox, out_root)

        plan = build_plan(inbox, out_root)

        if args.verify:
            checks = plan.audit()
            passed = sum(1 for _, ok in checks if ok)
            if not args.quiet:
                for name, ok in checks:
                    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
                print(f"\n  {passed}/{len(checks)} checks passed")
            return 0 if passed == len(checks) else 1

        if args.json:
            target = Path(args.json)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(plan.to_dict(), indent=2) + "\n",
                              encoding="utf-8")
            if not args.quiet:
                print(f"  wrote {len(plan)} move(s) to {target}")
            return 0

        if args.apply:
            if (args.inbox is None or args.out is None or
                    inbox.resolve() == INBOX.resolve() or
                    out_root.resolve() == OUT.resolve()):
                print("  refusing to move the bundled folders: pass --inbox "
                      "and --out", file=sys.stderr)
                return 2
            applied = apply_plan(plan)
            if not args.quiet:
                for move in applied:
                    print(f"  moved {move.source.name} -> {move.category}/"
                          f"{move.target.name}")
                print(f"\n  {len(applied)} file(s) moved, "
                      f"{plan.total_bytes} bytes")
            return 0

        if args.quiet:
            return 0

        _summary(plan)
        print()
        _show_plan(plan)
        return 0
    except OrganizeError as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
