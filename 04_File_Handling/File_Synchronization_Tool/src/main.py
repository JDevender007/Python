"""Command line for File_Synchronization_Tool.

    python src/main.py --demo
    python src/main.py                     # the plan, nothing copied
    python src/main.py --delete            # the plan, with the deletes named
    python src/main.py --verify
    python src/main.py --legacy
    python src/main.py --report plan.csv
    python src/main.py --json plan.json
    python src/main.py --apply [--delete] --source SRC --target DST
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import sync
from sync import (COPY, DELETE, DESTINATION, ORPHAN, SKIP, SOURCE, UPDATE,
                  SyncError, apply_plan, build_plan, legacy_mirror, problems,
                  scan_tree, verify_mirror)


def _show_plan(plan) -> None:
    for action, changes in plan.by_action().items():
        print(f"  {action}  ({len(changes)} file(s))")
        for change in changes:
            print(f"    {change.path:<28} {change.bytes:>7} bytes  "
                  f"{change.reason}")
    if not plan.changes:
        print("  nothing to do: the two trees already agree")


def _summary(plan) -> None:
    summary = plan.summary()
    print(f"  source       {plan.source}")
    print(f"  destination  {plan.dest}")
    print(f"  changes      {summary['changes']} "
          f"({summary['copy']} copy, {summary['update']} update, "
          f"{summary['skip']} skip, {summary['delete']} delete, "
          f"{summary['orphan']} orphan)")
    print(f"  to copy      {summary['bytes_to_copy']} bytes")
    print(f"  orphans      {summary['bytes_to_delete']} bytes "
          f"{'(will be deleted)' if summary['delete'] else '(left in place)'}")
    print(f"  hashed       {summary['hashes']} file(s)")


def _legacy(source, dest) -> int:
    report = legacy_mirror(source, dest)
    print(f"  the legacy loop would copy {len(report.copied)} file(s) and find "
          f"{len(report.already)} already equal, hashing {report.hashes} file(s)")
    for relative in report.copied:
        print(f"    copy   {relative}")
    for relative in report.already:
        print(f"    same   {relative}")
    orphans = sorted(set(scan_tree(dest)) - set(scan_tree(source)))
    print(f"  it would leave {len(orphans)} file(s) in the destination that "
          f"the source does not have: {', '.join(orphans) if orphans else 'none'}")
    print(f"  the lines are {sync.LEGACY_ALWAYS!r} and "
          f"{sync.LEGACY_NEVER_DELETES!r}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file-sync",
        description="Mirror one folder into another: plan every copy, update, "
                    "skip and delete before touching a file.")
    parser.add_argument("--source", default=None,
                        help="the folder to copy from (default: bundled)")
    parser.add_argument("--target", default=None,
                        help="the folder to mirror into (default: bundled)")
    parser.add_argument("--delete", action="store_true",
                        help="delete files the source does not have")
    parser.add_argument("--apply", action="store_true",
                        help="do the plan; without it nothing is written")
    parser.add_argument("--verify", action="store_true",
                        help="prove the destination is a mirror")
    parser.add_argument("--legacy", action="store_true",
                        help="what the legacy loop would do")
    parser.add_argument("--report", default=None, metavar="PATH",
                        help="write the plan as CSV to PATH")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the plan as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def _write_report(plan, path: Path) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Action", "Path", "Bytes", "Other", "Reason"])
    for change in plan.changes:
        writer.writerow([change.action, change.path, change.size,
                         "" if change.other_size is None else change.other_size,
                         change.reason])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if not args.quiet:
            return sync.run_demo()
        with contextlib.redirect_stdout(io.StringIO()):
            return sync.run_demo()

    source = Path(args.source) if args.source else SOURCE
    dest = Path(args.target) if args.target else DESTINATION

    try:
        if args.legacy:
            if not args.quiet:
                return _legacy(source, dest)
            with contextlib.redirect_stdout(io.StringIO()):
                return _legacy(source, dest)

        if args.verify:
            checks = verify_mirror(source, dest)
            passed = sum(1 for _, ok in checks if ok)
            if not args.quiet:
                for name, ok in checks:
                    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
                print(f"\n  {passed}/{len(checks)} checks passed")
            return 0 if passed == len(checks) else 1

        plan = build_plan(source, dest, delete=args.delete)

        if args.report:
            target = Path(args.report)
            _write_report(plan, target)
            if not args.quiet:
                print(f"  wrote {len(plan)} change(s) to {target}")
            return 0

        if args.json:
            target = Path(args.json)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(plan.to_dict(), indent=2) + "\n",
                              encoding="utf-8")
            if not args.quiet:
                print(f"  wrote {len(plan)} change(s) to {target}")
            return 0

        if args.apply:
            if (args.source is None or args.target is None or
                    source.resolve() == SOURCE.resolve() or
                    dest.resolve() == DESTINATION.resolve()):
                print("  refusing to write to the bundled folders: pass "
                      "--source and --target", file=sys.stderr)
                return 2
            applied = apply_plan(plan)
            if not args.quiet:
                for change in applied:
                    print(f"  {change.action:<6} {change.path}")
                print(f"\n  {len(applied)} change(s) applied, "
                      f"{plan.bytes_to_copy} bytes copied")
            left = problems(source, dest)
            if left:
                print(f"  the mirror still fails: {', '.join(left)}",
                      file=sys.stderr)
                return 1
            return 0

        if args.quiet:
            return 0

        _summary(plan)
        print()
        _show_plan(plan)
        return 0
    except SyncError as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
