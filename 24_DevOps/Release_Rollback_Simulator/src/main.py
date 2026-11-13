"""Command line entry point for the Release / Rollback Simulator.

Usage
-----
    python src/main.py --demo                        # three rollouts
    python src/main.py                               # bundled, latest release
    python src/main.py --release 1.6.0-rc1           # a specific release
    python src/main.py --strategy blue_green         # canary | rolling | blue_green
    python src/main.py --steps "5,50,100"            # custom traffic ladder
    python src/main.py --release 1.6.0 --json out.json

Exit codes: 0 = healthy (promoted or safely rolled back), 1 = unhealthy
(the service could not be left in a good state), 2 = usage or parse error.

Fully offline: a local deployment document in, a deterministic rollout out.
No cluster, no network, no API keys.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from rollout import (
    BUNDLED_DEPLOYMENT,
    STRATEGIES,
    RolloutError,
    execute,
    load_deployment,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("rollout")

BANNER = """
========================================
 RELEASE / ROLLBACK SIMULATOR
   canary, rolling, blue-green + SLO burn
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate a release rollout with health gates, "
                    "rollback and SLO error-budget accounting (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled three-rollout demo")
    parser.add_argument("--file", type=Path, default=BUNDLED_DEPLOYMENT,
                        help="deployment document (JSON); defaults to the "
                             "bundled sample")
    parser.add_argument("--release", default=None,
                        help="release version to roll out "
                             "(default: the newest in the document)")
    parser.add_argument("--strategy", default=None, choices=STRATEGIES,
                        help="traffic ladder to use (default: from the "
                             "document)")
    parser.add_argument("--steps", default=None,
                        help="custom comma-separated traffic ladder ending "
                             "at 100, e.g. \"5,50,100\"")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the rollout result as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def parse_steps(raw: str) -> tuple[int, ...]:
    """Turn "5,50,100" into (5, 50, 100), rejecting anything else early."""
    parts = [part.strip() for part in raw.split(",")]
    if not parts or any(not part for part in parts):
        raise RolloutError(f"--steps must be a comma-separated list of "
                           f"integers, got {raw!r}")
    steps = []
    for part in parts:
        try:
            steps.append(int(part))
        except ValueError as exc:
            raise RolloutError(f"--steps: {part!r} is not an integer") \
                from exc
    return tuple(steps)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if args.release or args.strategy or args.steps or args.json:
            parser.error("--demo cannot be combined with --release, "
                         "--strategy, --steps or --json")
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except RolloutError as exc:
            # the bundled document ships with the repo, so this is a broken
            # checkout rather than bad user input - report it, exit 0.
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    # validate cheap inputs before touching the file system
    steps = None
    if args.steps is not None:
        try:
            steps = parse_steps(args.steps)
        except RolloutError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    try:
        deployment = load_deployment(args.file)
    except RolloutError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    version = args.release or deployment.releases[-1].version
    if not args.quiet:
        print(BANNER)
    try:
        result = execute(deployment, version, args.strategy, steps)
    except RolloutError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result))
        print(f"\nDone: {result.state}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {"source": str(args.file), **result.to_dict()}
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    return 0 if result.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
