"""Command line entry point for Word2Vec From Scratch.

Usage
-----
    python src/main.py --demo                            # bundled corpus
    python src/main.py --corpus data/corpus.txt           # train + report
    python src/main.py --similar king                     # neighbours
    python src/main.py --analogy man king woman           # analogy
    python src/main.py --corpus FILE --dim 32 --epochs 20 --json model.json

Fully offline: a local corpus in, embeddings + similarity queries out.
No gensim, no pre-trained vectors, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from word2vec import (
    DIM,
    EPOCHS,
    NEGATIVES,
    WINDOW,
    Word2VecError,
    load_corpus,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("word2vec")

BANNER = """
========================================
 WORD2VEC FROM SCRATCH
   skip-gram + negative sampling
   pure NumPy, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train skip-gram word embeddings offline and query them")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="train on the bundled corpus and run all checks")
    mode.add_argument("--corpus", type=Path, default=None,
                      help="local text file to train on")
    parser.add_argument("--dim", type=int, default=DIM,
                        help=f"embedding dimension (default {DIM})")
    parser.add_argument("--epochs", type=int, default=EPOCHS,
                        help=f"training epochs (default {EPOCHS})")
    parser.add_argument("--window", type=int, default=WINDOW,
                        help=f"skip-gram window (default {WINDOW})")
    parser.add_argument("--negatives", type=int, default=NEGATIVES,
                        help=f"negative samples per pair (default {NEGATIVES})")
    parser.add_argument("--similar", metavar="WORD", default=None,
                        help="show nearest neighbours for WORD")
    parser.add_argument("--analogy", nargs=3, metavar=("A", "B", "C"),
                        default=None,
                        help="solve A : B :: C : ? (vectors B - A + C)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write model summary as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the report")
    return parser


def _validate(args, parser) -> None:
    if args.dim < 2:
        parser.error(f"--dim must be at least 2, got {args.dim}")
    if args.epochs < 1:
        parser.error(f"--epochs must be at least 1, got {args.epochs}")
    if args.window < 1:
        parser.error(f"--window must be at least 1, got {args.window}")
    if args.negatives < 1:
        parser.error(f"--negatives must be at least 1, got {args.negatives}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except Word2VecError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.corpus is None and args.similar is None and args.analogy is None:
        parser.error("one of the arguments --demo --corpus --similar "
                     "--analogy is required")

    # fast-fail: validate flags BEFORE reading or training
    _validate(args, parser)

    try:
        text = load_corpus(args.corpus)
    except Word2VecError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        model = train_model(text, dim=args.dim, window=args.window,
                            epochs=args.epochs, negatives=args.negatives)
    except Word2VecError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(f"Vocabulary     : {len(model.words)} words")
        print(f"Loss           : {model.losses[0]:.4f} -> "
              f"{model.losses[-1]:.4f}")

    if args.similar:
        try:
            for word, score in model.most_similar(args.similar):
                print(f"  {word:<12} {score:+.4f}")
        except Word2VecError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.analogy:
        a, b, c = args.analogy
        try:
            print(f"{a} : {b} :: {c} : ?")
            for word, score in model.analogy(a, b, c):
                print(f"  {word:<12} {score:+.4f}")
        except Word2VecError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(model.to_dict(), indent=2),
                             encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
