"""Command line entry point for the Digit Recognizer.

Usage
-----
    python src/main.py --demo                       # bundled data, full report
    python src/main.py --file digits.csv            # train on your own CSV
    python src/main.py --file digits.csv --epochs 30 --json metrics.json
    python src/main.py --predict "0,0,5,...,1"      # 64 pixel values 0..16

Fully offline: local CSV in, metrics + confusion matrix out. No network,
no dataset downloads (the bundled sample ships in data/).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from digits import (
    DEMO_CSV,
    DigitError,
    load_digits_data,
    render_report,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("digits")

BANNER = """
========================================
 DIGIT RECOGNIZER
   PyTorch MLP on 8x8 digits, offline
========================================
"""


def parse_pixels(text: str) -> list[float]:
    """Parse '0,0,5,...' (64 values, each 0..16) into a list."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) != 64:
        raise DigitError(f"expected 64 comma-separated pixel values, "
                         f"got {len(parts)}")
    values = []
    for i, part in enumerate(parts):
        try:
            number = float(part)
        except ValueError as exc:
            raise DigitError(f"not a number for pixel_{i}: {part!r}") from exc
        values.append(number)
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify 8x8 handwritten digits (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="train on the bundled digits sample")
    action.add_argument("--file", type=Path, default=None,
                        help="digits CSV (pixel_0..pixel_63,label) to train")
    parser.add_argument("--epochs", type=int, default=12,
                        help="training epochs (default 12)")
    parser.add_argument("--lr", type=float, default=1e-3,
                        help="Adam learning rate (default 0.001)")
    parser.add_argument("--batch", type=int, default=64,
                        help="mini-batch size (default 64)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed (default 42)")
    parser.add_argument("--predict", metavar="PIXELS", default=None,
                        help="classify one 8x8 image: 64 comma-separated "
                             "values 0..16 (uses --file, or the bundled "
                             "sample)")
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
        except DigitError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.file is None and args.predict is None:
        parser.error("one of the arguments --demo --file --predict is required")

    if not args.quiet:
        print(BANNER)
    try:
        # --predict without --file trains on the bundled sample
        frame = load_digits_data(args.file or DEMO_CSV)
        result = train_model(frame, epochs=args.epochs, lr=args.lr,
                             batch_size=args.batch, seed=args.seed)
    except DigitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result, frame))

    if args.predict is not None:
        try:
            pixels = parse_pixels(args.predict)
            label, confidence = result.predict(pixels)
        except DigitError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(f"\nPrediction: digit {label} "
              f"(confidence {confidence:.1%})")

    if args.json:
        payload = result.to_dict()
        if args.predict is not None:
            payload["prediction"] = {"label": label,
                                     "confidence": round(confidence, 4)}
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
