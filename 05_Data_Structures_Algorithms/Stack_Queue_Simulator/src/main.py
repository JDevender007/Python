"""Command line front end for the history lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from structures import (                                      # noqa: E402
    CAPACITY,
    KINDS,
    LEGACY_CALLBACKS,
    LEGACY_COUNTER,
    LEGACY_COUNTER_SITES,
    LEGACY_THEORY,
    HistoryError,
    Simulator,
    StructureError,
    ValidationError,
    audit,
    problems,
    read_session,
    run_demo,
    run_session,
)


def _show(simulator: Simulator, label: str) -> None:
    print(f"  {label}")
    snapshot = simulator.snapshot()
    for kind in KINDS:
        items = " ".join(snapshot[kind]) or "-"
        print(f"    {kind:<7}{items}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="history-lab",
        description="Run a session of stack, queue, deque and heap "
                    "operations, then undo and redo them -- because undo is a "
                    "second stack, not a method on the first.")
    parser.add_argument("--session", default=None,
                        help="a session file (default: the bundled session)")
    parser.add_argument("--capacity", type=int, default=CAPACITY,
                        help=f"items per structure (default: {CAPACITY})")
    parser.add_argument("--history", action="store_true",
                        help="print every recorded step")
    parser.add_argument("--undo", type=int, default=None, metavar="N",
                        help="undo N steps")
    parser.add_argument("--redo", type=int, default=None, metavar="N",
                        help="redo N steps")
    parser.add_argument("--undo-all", action="store_true",
                        help="undo every step")
    parser.add_argument("--redo-all", action="store_true",
                        help="redo every step")
    parser.add_argument("--legacy", action="store_true",
                        help="print the legacy claims, transcribed")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the state and history to PATH as JSON")
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
        lines = read_session(args.session) if args.session \
            else read_session()
        simulator = run_session(lines, Simulator(args.capacity))
    except ValidationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except StructureError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.undo is not None or args.undo_all:
        count = len(simulator.history) if args.undo_all else args.undo
        if count < 0:
            print("error: --undo needs a count of at least zero",
                  file=sys.stderr)
            return 2
        try:
            for _ in range(count):
                simulator.undo()
        except HistoryError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2

    if args.redo is not None or args.redo_all:
        count = len(simulator.future) if args.redo_all else args.redo
        if count < 0:
            print("error: --redo needs a count of at least zero",
                  file=sys.stderr)
            return 2
        try:
            for _ in range(count):
                simulator.redo()
        except HistoryError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2

    if args.quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            _show(simulator, "state:")
        return 0

    where = Path(args.session).name if args.session else "data/session.txt"
    print(f"  {where}: {len(lines)} lines, capacity {simulator.capacity}")
    print(f"  {simulator.applied} applied, {simulator.refused} refused, "
          f"{simulator.reads} reads, {simulator.undo_depth} undoable, "
          f"{simulator.redo_depth} redoable")
    print()
    _show(simulator, "state:")

    if args.history:
        print("\n  recorded steps, oldest first:")
        for step in simulator.history:
            print(f"    {step}")
        if simulator.future:
            print("  undone steps, replayable, oldest first:")
            for step in simulator.future:
                print(f"    {step}")

    if args.legacy:
        undo_callbacks = [name for name in LEGACY_CALLBACKS if "undo" in name]
        print("\n  the legacy theory panel said:")
        print(f"    \"{LEGACY_THEORY}...\"")
        print(f"  its control panel declared {len(LEGACY_CALLBACKS)} callbacks, "
              f"{len(undo_callbacks)} of which undo anything")
        print(f"  and it counted with {LEGACY_COUNTER!r}, at "
              f"{LEGACY_COUNTER_SITES} sites -- success and failure alike")

    if args.audit:
        print()
        checks = audit(simulator)
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
            "capacity": simulator.capacity,
            "state": {kind: list(items)
                      for kind, items in simulator.snapshot().items()},
            "counts": {"applied": simulator.applied,
                       "refused": simulator.refused,
                       "reads": simulator.reads,
                       "discarded": simulator.discarded,
                       "undoable": simulator.undo_depth,
                       "redoable": simulator.redo_depth},
            "history": [str(step) for step in simulator.history],
            "future": [str(step) for step in simulator.future],
        }
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        print(f"  wrote {len(simulator.history)} step(s) to {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
