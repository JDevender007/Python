"""Command line entry point for the CI Pipeline Simulator.

Usage
-----
    python src/main.py --demo
    python src/main.py --file data/pipeline.json
    python src/main.py --file data/pipeline.toml --fail unit=flaky
    python src/main.py --fail integration=hard --no-fail-fast --json run.json

Fully offline: a local pipeline document in, a deterministic simulated
run out. No network, no runner, no API keys.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pipeline import (
    BUNDLED_JSON,
    FAIL_MODES,
    PipelineError,
    dependency_depth,
    load_pipeline,
    render_report,
    run_demo,
    simulate,
    topological_order,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("pipeline")

BANNER = """
========================================
 CI PIPELINE SIMULATOR
   DAG stages, matrix jobs,
   fail-fast vs continue, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate a CI pipeline DAG offline")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled demo with self-checks")
    parser.add_argument("--file", type=Path, default=None,
                        help="pipeline document (.json or .toml); "
                             "default: bundled pipeline.json")
    parser.add_argument("--fail", action="append", default=None,
                        metavar="STAGE=MODE",
                        help="inject a failure: STAGE (or a job label) and "
                             "MODE, one of hard|flaky; repeatable")
    parser.add_argument("--no-fail-fast", action="store_true",
                        help="continue on failure instead of aborting")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the run report as JSON")
    parser.add_argument("--save", type=Path, default=None,
                        help="write the text report to a file")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def parse_failures(entries: list[str] | None,
                   parser: argparse.ArgumentParser) -> dict[str, str]:
    """Turn ['unit=flaky', ...] into {'unit': 'flaky'} with validation."""
    failures: dict[str, str] = {}
    for entry in entries or []:
        if "=" not in entry:
            parser.error(f"--fail needs STAGE=MODE, got {entry!r}")
        name, _, mode = entry.partition("=")
        name, mode = name.strip(), mode.strip().lower()
        if not name:
            parser.error(f"--fail needs a stage name, got {entry!r}")
        if mode not in FAIL_MODES:
            parser.error(f"unknown failure mode {mode!r} "
                         f"(choose from {', '.join(FAIL_MODES)})")
        if name in failures:
            parser.error(f"--fail given twice for {name!r}")
        failures[name] = mode
    return failures


def _payload(run, pipeline, source: Path) -> dict[str, Any]:
    payload = run.to_dict()
    payload["source"] = str(source)
    payload["dependency_depth"] = dependency_depth(pipeline)
    payload["stage_count"] = len(pipeline.stages)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    failures = parse_failures(args.fail, parser)

    if args.demo:
        if (failures or args.no_fail_fast or args.json is not None
                or args.save is not None):
            parser.error("--demo does not accept --fail, --no-fail-fast, "
                         "--json or --save")
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except PipelineError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.quiet:
        print(BANNER)

    source = args.file or BUNDLED_JSON
    try:
        # parse before simulating so bad input fails fast
        pipeline = load_pipeline(source)
        run = simulate(pipeline, failures, fail_fast=not args.no_fail_fast)
    except PipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print()
        print(render_report(run))

    if args.save is not None:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(render_report(run) + "\n", encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.save}")

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(_payload(run, pipeline, source), indent=2),
            encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print(f"\nOrder: {' -> '.join(topological_order(pipeline))}")
    return 0 if run.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
