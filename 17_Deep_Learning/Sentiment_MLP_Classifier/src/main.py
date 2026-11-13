"""Command line entry point for the Sentiment MLP Classifier.

Usage
-----
    python src/main.py --demo                       # bundled data, report
    python src/main.py --file messages.csv          # train on your own CSV
    python src/main.py --file messages.csv --epochs 80 --json metrics.json
    python src/main.py --classify "i love this movie"
    python src/main.py --classify "i hate this movie" --quiet

Fully offline: local CSV in, metrics + probabilities out. No network,
no dataset downloads (the bundled sample ships in data/).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sentiment import (
    DEMO_CSV,
    SentimentError,
    load_messages,
    render_report,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("sentiment")

BANNER = """
========================================
 SENTIMENT MLP CLASSIFIER
   bag-of-words + PyTorch MLP, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify message sentiment with a bag-of-words "
                    "MLP (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="train on the bundled messages sample")
    action.add_argument("--file", type=Path, default=None,
                        help="text,label CSV to train on")
    parser.add_argument("--epochs", type=int, default=40,
                        help="training epochs (default 40)")
    parser.add_argument("--lr", type=float, default=1e-3,
                        help="Adam learning rate (default 0.001)")
    parser.add_argument("--batch", type=int, default=32,
                        help="mini-batch size (default 32)")
    parser.add_argument("--dropout", type=float, default=0.1,
                        help="dropout rate (default 0.1)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed (default 42)")
    parser.add_argument("--classify", metavar="TEXT", default=None,
                        help="classify one message (uses --file, or the "
                             "bundled sample)")
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
        except SentimentError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.file is None and args.classify is None:
        parser.error("one of the arguments --demo --file --classify "
                     "is required")

    # validate the message up front so bad input fails fast
    message: str | None = None
    if args.classify is not None:
        if not args.classify.strip():
            print("Error: --classify message must be non-empty",
                  file=sys.stderr)
            return 2
        message = args.classify

    if not args.quiet:
        print(BANNER)
    try:
        # --classify without --file trains on the bundled sample
        frame = load_messages(args.file or DEMO_CSV)
        result = train_model(frame, epochs=args.epochs, lr=args.lr,
                             batch_size=args.batch, dropout=args.dropout,
                             seed=args.seed)
    except SentimentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result))

    if message is not None:
        try:
            label, probability = result.predict(message)
        except SentimentError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        sentiment = "POSITIVE" if label == 1 else "NEGATIVE"
        print(f"\nSentiment: {sentiment} "
              f"(p={probability:.3f})  {message!r}")

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
