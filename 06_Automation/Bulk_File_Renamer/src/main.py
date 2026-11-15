"""Command line front end for the rename lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from renamer import (                                         # noqa: E402
    FOLDER_FILE,
    NAMES_FILE,
    PlanError,
    RenameError,
    UndoError,
    apply,
    audit,
    build_plan,
    problems,
    read_folder,
    read_lines,
    run_demo,
    undo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rename-lab",
        description="Build a rename plan from a folder and a list of names, "
                    "check it, then apply and undo it -- without ever leaving "
                    "half the folder renamed.")
    parser.add_argument("--folder", default=None,
                        help="a folder file (default: the bundled one)")
    parser.add_argument("--names", default=None,
                        help="a name list (default: the bundled one)")
    parser.add_argument("--short", type=int, default=None, metavar="N",
                        help="use only the first N names, to see the plan "
                             "refuse a list that does not cover the folder")
    parser.add_argument("--apply", action="store_true",
                        help="apply the plan in memory and list the result")
    parser.add_argument("--undo", type=int, default=None, metavar="N",
                        help="after applying, undo the last N renames")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the plan and result to PATH as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing")
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
        folder = read_folder(args.folder) if args.folder else read_folder()
        names = read_lines(args.names) if args.names else read_lines()
    except PlanError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    # The audit judges the plan against the folder as it was; `folder` is the
    # one that gets renamed, so keep an untouched copy of the same contents.
    original = read_folder(args.folder) if args.folder else read_folder()

    if args.short is not None:
        if args.short < 0:
            print("error: --short needs a count of at least zero",
                  file=sys.stderr)
            return 2
        names = names[:args.short]

    try:
        plan = build_plan(folder, names)
    except PlanError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    records = ()
    if args.apply or args.undo is not None:
        try:
            records = apply(folder, plan)
        except RenameError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2

    if args.undo is not None:
        if args.undo < 1:
            print("error: --undo needs a count of at least one",
                  file=sys.stderr)
            return 2
        try:
            undo(folder, records[-args.undo:])
        except UndoError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        records = records[:-args.undo]

    if args.quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            for line in plan.lines():
                print(line)
        return 0

    where = Path(args.folder).name if args.folder else "data/folder.txt"
    print(f"  {where}: {len(folder)} files, {len(names)} names")
    print("  plan:")
    for line in plan.lines():
        print(f"    {line}")

    if records:
        print(f"  applied {len(records)} rename(s); the folder now holds:")
        for name in folder.names():
            print(f"    {name}")
        print(f"  {len(records)} record(s) kept, so undo needs "
              f"{len(records)}")
    elif args.apply:
        print("  nothing to apply: every name is already the one asked for")

    if args.audit:
        print()
        checks = audit(original, plan, records)
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)
        if failed:
            print(f"  {len(failed)} check(s) failed", file=sys.stderr)
            return 1

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "files": list(folder.names()),
            "names": list(names),
            "plan": [{"old": entry.old, "wanted": entry.wanted,
                      "new": entry.new, "note": entry.note}
                     for entry in plan],
            "applied": [{"old": record.old, "new": record.new}
                        for record in records],
            "notes": list(plan.notes()),
        }
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        print(f"  wrote {len(plan)} plan entr(ies) to {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
