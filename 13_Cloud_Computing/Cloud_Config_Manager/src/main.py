"""Command line front end for the cloud config lab.

Usage:
    python src/main.py --demo
    python src/main.py --demo --quiet
    python src/main.py --file data/desired.json --json out.json
    python src/main.py --file data/desired.json --audit
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

from config_manager import (                                # noqa: E402
    ConfigError,
    audit,
    measure,
    render_plan,
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
        prog="config-lab",
        description="Merge and diff bundled cloud configs offline, with secrets masked.",
    )
    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    parser.add_argument("--quiet", action="store_true", help="with --demo, print nothing")
    parser.add_argument(
        "--file",
        default=None,
        metavar="DESIRED_JSON",
        help="desired config; override.json and observed.json are read from the same folder",
    )
    parser.add_argument(
        "--override", default=None, metavar="OVERRIDE_JSON", help="an explicit overlay document"
    )
    parser.add_argument(
        "--observed", default=None, metavar="OBSERVED_JSON", help="an explicit observed state"
    )
    parser.add_argument("--json", default=None, metavar="PATH", help="write a JSON report")
    parser.add_argument("--audit", action="store_true", help="re-run the checks; exit 1 on failure")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except ConfigError as exc:
            if not args.quiet:
                print(f"error: {exc}", file=sys.stderr)
            return 0

    desired = args.file
    override = args.override
    observed = args.observed
    if desired is not None:
        folder = Path(desired).resolve().parent
        override = override or folder / "override.json"
        observed = observed or folder / "observed.json"
    try:
        measured = measure(desired, override, observed)
    except ConfigError as exc:
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
        print(render_plan(measured["plan"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
