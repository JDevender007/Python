"""Command line entry point for the Model Evaluation Harness.

Usage
-----
    python src/main.py --demo                       # bundled data, all models
    python src/main.py --file dataset.csv           # your own dataset
    python src/main.py --file dataset.csv --folds 8 # custom CV folds
    python src/main.py --file dataset.csv --json comparison.json
    python src/main.py --list                       # model registry

Fully offline: local CSV in, comparison table out. No network, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from harness import (
    DEMO_CSV,
    MODELS,
    HarnessError,
    load_dataset,
    render_report,
    run_demo,
    run_harness,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("harness")

BANNER = """
========================================
 MODEL EVALUATION HARNESS
   stratified CV model comparison
========================================
"""


def _run_demo(quiet: bool, func, *args, **kwargs) -> int:
    """Run the offline demo; with --quiet no stream prints anything."""
    if not quiet:
        return func(*args, **kwargs)
    # --quiet: silence the demo's own prints and its log records alike, so a
    # scripted run writes nothing to stdout or stderr.
    level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(level)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare classifiers with stratified k-fold "
                    "cross-validation (offline)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="evaluate every model on the bundled sample")
    action.add_argument("--file", type=Path, default=None,
                        help="binary-label dataset to evaluate")
    action.add_argument("--list", action="store_true",
                        help="list the model registry")
    parser.add_argument("--folds", type=int, default=5,
                        help="CV folds (2-10, default 5)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed for splits (default 42)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the comparison as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print(BANNER)
        for name, (_, description) in MODELS.items():
            print(f"  {name:<22} {description}")
        print(f"\n{len(MODELS)} models available.")
        return 0

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo, folds=args.folds)
        except HarnessError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if not args.quiet:
        print(BANNER)
    try:
        frame = load_dataset(args.file)
        result = run_harness(frame, folds=args.folds, seed=args.seed)
    except HarnessError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result, frame))

    if args.json:
        payload = result.to_dict()
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
