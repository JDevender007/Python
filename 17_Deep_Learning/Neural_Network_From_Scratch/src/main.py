"""Command line entry point for the Neural Network From Scratch.

Usage
-----
    python src/main.py --demo                    # bundled data, full report
    python src/main.py --file dataset.csv        # train on your own CSV
    python src/main.py --file dataset.csv --layers 32,16 --epochs 500
    python src/main.py --file dataset.csv --json metrics.json

Fully offline: local CSV in, learning curve + hold-out metrics out.
No network, no downloads, no deep-learning framework.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from mlp import (
    DEMO_CSV,
    MLPError,
    load_data,
    render_report,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("mlp")

BANNER = """
========================================
 NEURAL NETWORK FROM SCRATCH
   pure-NumPy backprop, offline
========================================
"""


def parse_layers(text: str) -> tuple[int, ...]:
    """Parse '16,16' into (16, 16)."""
    try:
        layers = tuple(int(part.strip()) for part in text.split(",")
                       if part.strip())
    except ValueError as exc:
        raise MLPError(f"layers must be comma-separated integers: "
                       f"{text!r}") from exc
    if not layers or any(size < 1 for size in layers):
        raise MLPError(f"layer sizes must be positive integers: {text!r}")
    return layers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a pure-NumPy MLP on 2-D binary data (offline)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="train on the bundled circles sample")
    action.add_argument("--file", type=Path, default=None,
                        help="x1,x2,label CSV to train on")
    parser.add_argument("--layers", default="16,16",
                        help="hidden layer sizes, e.g. 32,16 (default 16,16)")
    parser.add_argument("--epochs", type=int, default=300,
                        help="training epochs (default 300)")
    parser.add_argument("--lr", type=float, default=0.1,
                        help="learning rate (default 0.1)")
    parser.add_argument("--batch", type=int, default=32,
                        help="mini-batch size (default 32)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed (default 42)")
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
        except MLPError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    try:
        hidden = parse_layers(args.layers)
    except MLPError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
    try:
        frame = load_data(args.file)
        result = train_model(frame, hidden=hidden, lr=args.lr,
                             epochs=args.epochs, batch_size=args.batch,
                             seed=args.seed)
    except MLPError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result))

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
