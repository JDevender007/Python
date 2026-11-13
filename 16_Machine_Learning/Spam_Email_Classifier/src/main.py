"""Command line entry point for the Spam Email Classifier.

Usage
-----
    python src/main.py --demo                       # bundled data, full report
    python src/main.py --file messages.csv          # train on your own CSV
    python src/main.py --classify "win a FREE prize" # classify one message
    python src/main.py --file messages.csv --json metrics.json

Fully offline: local CSV in, labels + probabilities out. No network.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from spam_classifier import (
    DEMO_CSV,
    SpamError,
    classify,
    load_messages,
    render_report,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("spam")

BANNER = """
========================================
 SPAM EMAIL CLASSIFIER
   bag-of-words + Naive Bayes, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify messages as spam/ham (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="train on the bundled sample")
    action.add_argument("--file", type=Path, default=None,
                        help="labelled message CSV to train on")
    parser.add_argument("--classify", metavar="TEXT", default=None,
                        help="classify one message (uses --file, or the "
                             "bundled sample)")
    parser.add_argument("--test-size", type=float, default=0.25,
                        help="hold-out fraction (default 0.25)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed for the split (default 42)")
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
        except SpamError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.file is None and args.classify is None:
        parser.error("one of the arguments --demo --file --classify "
                     "is required")

    if not args.quiet:
        print(BANNER)
    try:
        # --classify without --file trains on the bundled sample
        frame = load_messages(args.file or DEMO_CSV)
        result = train_model(frame, test_size=args.test_size,
                             seed=args.seed)
    except SpamError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result, frame))

    if args.classify is not None:
        try:
            label, probability = classify(result, args.classify)
        except SpamError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        verdict = "SPAM" if label == "spam" else "HAM"
        print(f"\nVerdict: {verdict} "
              f"(spam probability {probability:.1%})")
        print(f"  text: {args.classify[:70]}")

    if args.json:
        payload = result.to_dict()
        if args.classify is not None:
            payload["classification"] = {
                "label": label,
                "spam_probability": round(probability, 4),
            }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
