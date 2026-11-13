"""Command line entry point for the Time Series Predictor.

Usage
-----
    python src/main.py --demo                       # bundled series, report
    python src/main.py --file series.csv            # train on your own CSV
    python src/main.py --file series.csv --window 60 --epochs 50
    python src/main.py --file series.csv --forecast # next-step prediction
    python src/main.py --file series.csv --json metrics.json

Fully offline: local CSV in, metrics + forecasts out. No network.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from predictor import (
    DEMO_CSV,
    SeriesError,
    load_series,
    render_report,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("series")

BANNER = """
========================================
 TIME SERIES PREDICTOR
   LSTM next-step forecasting, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Forecast the next value of a univariate series "
                    "with an LSTM (offline)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="forecast the bundled sine series")
    action.add_argument("--file", type=Path, default=None,
                        help="t,value CSV to train on")
    parser.add_argument("--window", type=int, default=40,
                        help="look-back window (default 40)")
    parser.add_argument("--epochs", type=int, default=12,
                        help="training epochs (default 12)")
    parser.add_argument("--lr", type=float, default=5e-3,
                        help="Adam learning rate (default 0.005)")
    parser.add_argument("--hidden", type=int, default=32,
                        help="LSTM hidden size (default 32)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed (default 42)")
    parser.add_argument("--forecast", action="store_true",
                        help="print the next-step forecast after training")
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
        except SeriesError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.quiet:
        print(BANNER)
    try:
        frame = load_series(args.file)
        result = train_model(frame, window=args.window,
                             epochs=args.epochs, lr=args.lr,
                             hidden=args.hidden, seed=args.seed)
    except SeriesError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result))

    if args.forecast:
        tail = frame["value"].to_numpy(dtype=float)[-result.window:]
        try:
            next_value = result.forecast(tail)
        except SeriesError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(f"\nNext-step forecast after t={result.rows - 1}: "
              f"{next_value:.3f}")

    if args.json:
        payload = result.to_dict()
        if args.forecast:
            payload["forecast"] = round(next_value, 4)
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
