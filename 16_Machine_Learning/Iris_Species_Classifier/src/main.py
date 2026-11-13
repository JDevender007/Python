"""Command line entry point for the Iris Species Classifier.

Usage
-----
    python src/main.py --demo                      # bundled data, full report
    python src/main.py --file iris.csv             # train on your own CSV
    python src/main.py --file iris.csv --k 7       # custom neighbour count
    python src/main.py --predict "5.1,3.5,1.4,0.2" # classify one flower
    python src/main.py --file iris.csv --json metrics.json

Fully offline: local CSV in, metrics out. No network, no downloads.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from iris_classifier import (
    DEMO_CSV,
    FEATURES,
    IrisError,
    load_iris,
    predict_species,
    render_report,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("iris")

BANNER = """
========================================
 IRIS SPECIES CLASSIFIER (k-NN)
   offline training and evaluation
========================================
"""


def parse_measurements(text: str) -> dict[str, float]:
    """Parse '5.1,3.5,1.4,0.2' into a measurement dict (feature order)."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) != len(FEATURES):
        raise IrisError(
            f"expected {len(FEATURES)} comma-separated numbers "
            f"({', '.join(FEATURES)}), got {len(parts)}"
        )
    values: dict[str, float] = {}
    for feature, part in zip(FEATURES, parts):
        try:
            values[feature] = float(part)
        except ValueError as exc:
            raise IrisError(f"not a number for {feature}: {part!r}") from exc
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train and evaluate a k-NN iris classifier (offline)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="train on the bundled sample")
    action.add_argument("--file", type=Path, default=None,
                        help="iris CSV to train on")
    parser.add_argument("--k", type=int, default=5,
                        help="neighbours for k-NN (default 5)")
    parser.add_argument("--test-size", type=float, default=0.25,
                        help="hold-out fraction (default 0.25)")
    parser.add_argument("--predict", metavar="MEASUREMENTS", default=None,
                        help="classify one flower: '5.1,3.5,1.4,0.2'")
    parser.add_argument("--json", type=Path, default=None,
                        help="write metrics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            run_demo()
        except IrisError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.quiet:
        print(BANNER)
    try:
        frame = load_iris(args.file)
        result = train_model(frame, neighbors=args.k,
                             test_size=args.test_size)
    except IrisError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result, frame))

    if args.predict:
        try:
            measurements = parse_measurements(args.predict)
            species = predict_species(result.model, measurements)
        except IrisError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(f"\nPrediction: {args.predict} -> {species}")

    if args.json:
        payload = result.to_dict()
        if args.predict:
            payload["prediction"] = species
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
