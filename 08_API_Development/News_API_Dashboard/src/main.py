"""Command line front end for the envelope lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from envelopes import (                                     # noqa: E402
    KINDS,
    Response,
    ResponseError,
    audit,
    classify,
    legacy_of,
    problems,
    read_all,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="envelope-lab",
        description="Classify a response by its status AND its body, so an "
                    "empty list is never mistaken for an answer.")
    parser.add_argument("--responses", default=None, metavar="PATH",
                        help="a bundle of responses (default: the bundled one)")
    parser.add_argument("--name", default=None,
                        help="read one response by name")
    parser.add_argument("--body", default=None, metavar="TEXT",
                        help="classify one body as if it arrived with --status")
    parser.add_argument("--status", default=200, type=int, metavar="N",
                        help="the status for --body (default: 200)")
    parser.add_argument("--kind", default=None, choices=KINDS,
                        help="list only the outcomes of one kind")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the outcomes to PATH as JSON")
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

    if args.body is not None:
        try:
            outcome = classify(Response("inline", args.status, args.body))
        except ResponseError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"  {outcome.line()}")
            print("  the legacy reader answers "
                  f"{legacy_of((args.body,))[0]!r} for the same bytes")
        if outcome.kind in ("error", "malformed"):
            print(f"error: {outcome.note}", file=sys.stderr)
            return 2
        return 0

    try:
        bundle, responses = read_all(args.responses)
    except (ResponseError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.name is not None:
        try:
            outcome = bundle.by_name(args.name)
        except ResponseError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"  {outcome.sentence()}")
            for title in outcome.titles():
                print(f"    {title}")
        if outcome.kind in ("error", "malformed"):
            return 2
        return 0

    shown = bundle.outcomes
    if args.kind is not None:
        shown = bundle.of_kind(args.kind)

    if not args.quiet:
        counts = bundle.counts()
        print(f"  {len(bundle)} response(s): "
              + ", ".join(f"{counts[kind]} {kind}" for kind in KINDS))
        for outcome in shown:
            print(f"    {outcome.line()}")
        legacy = legacy_of(tuple(response.body for response in responses))
        empties = [response.name for response, value in zip(responses, legacy)
                   if value == []]
        print(f"  the legacy reader answers exactly [] for {len(empties)} of "
              f"them: {', '.join(empties)}")

    failed_checks = []
    checks: list[tuple[str, bool]] = []
    if args.audit:
        checks = audit(bundle, responses)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "counts": bundle.counts(),
            "outcomes": [
                {
                    "name": outcome.name,
                    "status": outcome.status,
                    "kind": outcome.kind,
                    "count": len(outcome),
                    "total": outcome.total,
                    "shortfall": outcome.shortfall(),
                    "titles": list(outcome.titles()),
                    "note": outcome.note,
                }
                for outcome in bundle.outcomes
            ],
            "legacy": [
                {"name": response.name,
                 "value": value if value != "crash" else None,
                 "crashed": value == "crash"}
                for response, value in
                zip(responses, legacy_of(tuple(response.body
                                               for response in responses)))
            ],
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the outcomes to {destination}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
