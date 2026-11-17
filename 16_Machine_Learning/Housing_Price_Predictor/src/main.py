"""Command line entry point for the Housing Price Predictor.

Usage
-----
    python src/main.py --demo                       # bundled data, full report
    python src/main.py --file housing.csv           # train on your own CSV
    python src/main.py --file housing.csv --json metrics.json
    python src/main.py --predict "180,5,3,3.0,12,1,1,Central"

Fully offline: local CSV in, metrics out. No network, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from housing import (
    DEMO_CSV,
    DISTRICTS,
    NUMERIC,
    HousingError,
    load_housing,
    predict_price,
    render_report,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("housing")

BANNER = """
========================================
 HOUSING PRICE PREDICTOR
   offline regression comparison
========================================
"""


def parse_house(text: str) -> dict:
    """Parse '180,5,3,3.0,12,1,1,Central' into a house dict.

    Field order: size_sqm, rooms, age_years, dist_km, floor, has_lift,
    has_garden, district.
    """
    parts = [p.strip() for p in text.split(",") if p.strip()]
    expected = len(NUMERIC) + 1  # + district
    if len(parts) != expected:
        raise HousingError(
            f"expected {expected} comma-separated values "
            f"({', '.join(NUMERIC)}, district), got {len(parts)}"
        )
    values: dict = {}
    for column, part in zip(NUMERIC, parts):
        try:
            number = float(part)
        except ValueError as exc:
            raise HousingError(f"not a number for {column}: {part!r}") from exc
        values[column] = int(number) if column in (
            "rooms", "floor", "has_lift", "has_garden") else number
    district = parts[-1]
    if district.title() not in DISTRICTS:
        raise HousingError(
            f"unknown district {district!r} (expected {', '.join(DISTRICTS)})")
    values["district"] = district.title()
    return values


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
        description="Compare linear regression vs random forest on housing "
                    "prices (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="train on the bundled sample")
    action.add_argument("--file", type=Path, default=None,
                        help="housing CSV to train on")
    parser.add_argument("--predict", metavar="HOUSE", default=None,
                        help="predict one house: '180,5,3,3.0,12,1,1,Central' "
                             "(uses --file, or the bundled sample)")
    parser.add_argument("--test-size", type=float, default=0.25,
                        help="hold-out fraction (default 0.25)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed for the split/forest (default 42)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write metrics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except HousingError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.file is None and args.predict is None:
        parser.error("one of the arguments --demo --file --predict is required")

    if not args.quiet:
        print(BANNER)
    try:
        # --predict without --file trains on the bundled sample
        frame = load_housing(args.file or DEMO_CSV)
        result = train_model(frame, seed=args.seed,
                             test_size=args.test_size)
    except HousingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result, frame))

    if args.predict:
        try:
            house = parse_house(args.predict)
            predicted = predict_price(result, house)
        except HousingError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(f"\nPrediction: {args.predict} -> ${predicted:,.0f}")

    if args.json:
        payload = result.to_dict()
        if args.predict:
            payload["prediction"] = round(predicted, 2)
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
