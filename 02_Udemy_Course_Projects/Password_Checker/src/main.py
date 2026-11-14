"""Command line interface for the password policy checker.

    python src/main.py --demo
    python src/main.py --check "Tr0ub4dor&3"
    python src/main.py --check "P@ssw0rd!" --identity alice
    python src/main.py --check "abc1" --policy relaxed
    python src/main.py --list-common
    python src/main.py --legacy myPass:MYPASS
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from policy import (
    Policy,
    PolicyError,
    check,
    legacy_verdict,
    load_common,
    run_demo,
)

BANNER = """
====================================
 PASSWORD CHECKER
   length, classes, patterns, words
====================================
"""

PROFILES = {
    "relaxed": Policy(min_length=4, min_classes=2, min_entropy=10.0,
                      forbid_common=False, forbid_sequences=False,
                      forbid_repeats=False, forbid_username=False),
    "default": Policy(),
    "strict": Policy(min_length=12, min_classes=4, min_entropy=60.0),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a password against a stated policy.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--check", metavar="PASSWORD",
                        help="check one password")
    parser.add_argument("--identity", metavar="USER",
                        help="username or email the password must not contain")
    parser.add_argument("--policy", choices=sorted(PROFILES),
                        default="default", help="named policy profile")
    parser.add_argument("--min-length", type=int, metavar="N",
                        help="override the profile's minimum length")
    parser.add_argument("--min-classes", type=int, metavar="N",
                        help="override the profile's minimum class count")
    parser.add_argument("--min-entropy", type=float, metavar="BITS",
                        help="override the profile's entropy floor")
    parser.add_argument("--list-common", action="store_true",
                        help="print the bundled common-password list")
    parser.add_argument("--legacy", metavar="OLD:NEW",
                        help="show what the original program would print")
    parser.add_argument("--json", metavar="PATH",
                        help="write the result as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="write no standard output")
    args = parser.parse_args(argv)

    if args.demo:
        if args.quiet:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo()
        else:
            run_demo()
        return 0

    try:
        if args.legacy is not None:
            if ":" not in args.legacy:
                raise PolicyError("expected OLD:NEW")
            old, new = args.legacy.split(":", 1)
            payload = {"mode": "legacy", "old_length": len(old),
                       "new_length": len(new),
                       "verdict": legacy_verdict(old, new),
                       "changed": old != new}
            if not args.quiet:
                print(BANNER)
                print(f"  old  {len(old)} character(s)")
                print(f"  new  {len(new)} character(s)")
                print(f"  says {payload['verdict']!r}")
                if payload["verdict"] == "Password Changed" and old == new:
                    print("  note: the two passwords are identical, so "
                          "nothing changed")
            if args.json:
                Path(args.json).write_text(json.dumps(payload, indent=2),
                                           encoding="utf-8")
            return 0

        if args.list_common:
            entries = sorted(load_common())
            payload = {"mode": "list-common", "count": len(entries),
                       "entries": entries}
            if not args.quiet:
                print(BANNER)
                for entry in entries:
                    print(f"  {entry}")
                print(f"\n  {len(entries)} entries")
            if args.json:
                Path(args.json).write_text(json.dumps(payload, indent=2),
                                           encoding="utf-8")
            return 0

        if args.check is None:
            parser.print_usage(sys.stderr)
            print("error: either --demo, --check, --list-common or --legacy "
                  "is required", file=sys.stderr)
            return 2

        policy = PROFILES[args.policy]
        overrides: dict = {}
        if args.min_length is not None:
            overrides["min_length"] = args.min_length
        if args.min_classes is not None:
            overrides["min_classes"] = args.min_classes
        if args.min_entropy is not None:
            overrides["min_entropy"] = args.min_entropy
        if overrides:
            policy = dataclasses.replace(policy, **overrides)

        verdict = check(args.check, policy, args.identity)
        payload = {"mode": "check", "profile": args.policy,
                   "verdict": verdict.to_dict()}

        if not args.quiet:
            print(BANNER)
            print(f"  length     {verdict.length}")
            print(f"  classes    {', '.join(verdict.classes) or 'none'}")
            print(f"  entropy    {verdict.entropy_bits} bits "
                  f"(observed-pool upper bound)")
            print(f"  score      {verdict.score}/100 ({verdict.label})")
            if verdict.accepted:
                print("  verdict    accepted")
            else:
                print(f"  verdict    rejected ({len(verdict.findings)} "
                      f"finding(s))")
                for finding in verdict.findings:
                    print(f"    - {finding.code}: {finding.message}")

        if args.json:
            Path(args.json).write_text(json.dumps(payload, indent=2),
                                       encoding="utf-8")
        return 0 if verdict.accepted else 1
    except PolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
