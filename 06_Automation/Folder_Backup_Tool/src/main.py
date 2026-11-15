"""Command line front end for the backup lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backup import (                                        # noqa: E402
    AFTER_FILE,
    BACKUP_FILE,
    BackupError,
    audit,
    build_session,
    count_only,
    next_name,
    problems,
    read_tree,
    run_demo,
    verify,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backup-lab",
        description="Verify a folder against a backup by path, size and "
                    "digest, plan an incremental copy, and name a backup "
                    "without merging it.")
    parser.add_argument("--source", default=None, metavar="PATH",
                        help="the folder as it is now (default: the bundled "
                             "one)")
    parser.add_argument("--backup", default=None, metavar="PATH",
                        help="the backup to verify (default: the bundled one)")
    parser.add_argument("--previous", default=None, metavar="PATH",
                        help="the previous backup to plan against (default: "
                             "the source)")
    parser.add_argument("--name", default=None, metavar="BASE",
                        help="print the first free backup name for BASE")
    parser.add_argument("--taken", default="", metavar="A,B",
                        help="names already in use, separated by commas")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the whole session to PATH as JSON")
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
        source = read_tree(args.source) if args.source else read_tree()
        backup = read_tree(args.backup) if args.backup else \
            read_tree(BACKUP_FILE)
        previous = read_tree(args.previous) if args.previous else \
            (read_tree(AFTER_FILE) if not args.source else source)
        taken = [name.strip() for name in args.taken.split(",") if name.strip()]
        session = build_session(source, backup, previous, taken)
        chosen = next_name(args.name, taken) if args.name else ""
    except BackupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    verdict, step = session.verdict, session.plan

    if not args.quiet:
        print(f"  {len(source)} file(s) in the source, {len(backup)} in the "
              f"backup, {len(previous)} in the previous backup")
        print(f"  the legacy count check says {count_only(source, backup)}")
        print(f"  verify: {verdict.summary()}")
        for line in verdict.lines():
            print(f"    {line}")
        print(f"  the backup is what it claims to be: {verdict.ok()}")

        print(f"  plan against the previous backup: {step.summary()}")
        for line in step.lines():
            print(f"    {line}")

        if args.name:
            print(f"  the first free name for {args.name!r} is {chosen!r}")

    failed_checks = []
    if args.audit:
        print()
        checks = audit(session)
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source": [{"path": entry.path, "size": entry.size,
                        "digest": entry.digest} for entry in source.manifest()],
            "backup": [{"path": entry.path, "size": entry.size,
                        "digest": entry.digest} for entry in backup.manifest()],
            "legacy_count_passes": count_only(source, backup),
            "verify": {
                "checked": verdict.checked,
                "identical": verdict.identical,
                "mismatches": verdict.mismatches(),
                "extras": verdict.extras(),
                "ok": verdict.ok(),
                "differences": [{"path": entry.path, "kind": entry.kind,
                                 "detail": entry.detail}
                                for entry in verdict.differences],
            },
            "plan": {
                "added": list(step.added),
                "changed": list(step.changed),
                "removed": list(step.removed),
                "unchanged": list(step.unchanged),
            },
            "name": chosen,
            "taken": list(session.taken),
        }
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the session to {target}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
