"""Command line front end for the event-queue lab.

Usage:
    python src/main.py --demo
    python src/main.py --demo --quiet
    python src/main.py --file data/scenario.json --json out.json
    python src/main.py --file data/scenario.json --audit
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from event_queue import (                                   # noqa: E402
    QueueError,
    audit,
    measure,
    render_timeline,
    report,
    run_demo,
)


def _run_demo(quiet: bool, func, *args, **kwargs) -> int:
    """Run the offline demo; with --quiet no stream prints anything."""
    if not quiet:
        return func(*args, **kwargs)
    level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(level)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="event-queue-lab",
        description="Replay an at-least-once queue over a bundled offline scenario.",
    )
    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    parser.add_argument("--quiet", action="store_true", help="with --demo, print nothing")
    parser.add_argument(
        "--file",
        default=None,
        metavar="SCENARIO_JSON",
        help="scenario to replay; defaults to data/scenario.json",
    )
    parser.add_argument("--json", default=None, metavar="PATH", help="write a JSON report")
    parser.add_argument("--audit", action="store_true", help="re-run the checks; exit 1 on failure")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo, args.file)
        except QueueError as exc:
            if not args.quiet:
                print(f"error: {exc}", file=sys.stderr)
            return 0

    try:
        measured = measure(args.file)
    except QueueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.audit:
        results = audit(measured)
        for name, okay in results:
            print(f"{'PASS' if okay else 'FAIL'}  {name}")
        failed = [name for name, okay in results if not okay]
        if failed:
            print(f"error: {len(failed)} check(s) failed", file=sys.stderr)
            return 1
        return 0

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report(measured), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if not args.quiet:
        run = measured["run"]
        print(
            f"events: {len(run.events)} | deliveries: {run.delivered} | "
            f"duplicates: {run.duplicates} | dead-lettered: {len(run.dead)}"
        )
        print()
        print(f"{'Event':<8} {'Attempt':>7} {'Worker':>6} {'Start':>5} {'End':>5}  Result")
        for item in run.deliveries:
            print(
                f"{item.event:<8} {item.attempt:>7} {item.worker:>6} "
                f"{item.started:>5} {item.finished:>5}  {item.outcome}"
            )
        print()
        if run.dead:
            for item in run.dead:
                print(f"dead-letter  {item.event}  attempts {item.attempts}  at {item.at}s")
            print()
        print(render_timeline(run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
