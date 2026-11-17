"""Command line entry point for the Markov Text Generator.

Usage
-----
    python src/main.py --demo                          # bundled corpus
    python src/main.py --corpus data/corpus.txt        # train + report
    python src/main.py --order 2 --length 40 --seed 7  # sampled text
    python src/main.py --corpus FILE --json run.json

Fully offline: a local corpus in, transition statistics and sampled text
out. No network, no downloads (the bundled corpus ships in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from markov import (
    DEFAULT_LENGTH,
    DEFAULT_ORDER,
    MAX_ORDER,
    MIN_ORDER,
    MarkovError,
    build_model,
    detokenize,
    generate_text,
    load_corpus,
    perplexity,
    run_demo,
    to_dict,
    tokenize,
    transition_report,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("markov")

BANNER = """
========================================
 MARKOV TEXT GENERATOR
   order-n transitions + backoff
   standard library only, offline
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
        description="Build a Markov chain from a local corpus and sample text")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="run the offline demo on the bundled corpus")
    mode.add_argument("--corpus", type=Path, default=None,
                      help="local text file to train on")
    parser.add_argument("--order", type=int, default=DEFAULT_ORDER,
                        help=f"chain order {MIN_ORDER}-{MAX_ORDER} "
                             f"(default {DEFAULT_ORDER})")
    parser.add_argument("--length", type=int, default=DEFAULT_LENGTH,
                        help=f"tokens to generate (default {DEFAULT_LENGTH})")
    parser.add_argument("--seed", type=int, default=0,
                        help="sampling seed (default 0)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write model statistics and sample as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except MarkovError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.corpus is None:
        parser.error("one of the arguments --demo --corpus is required")

    # fast-fail: validate flags before touching the corpus
    if not MIN_ORDER <= args.order <= MAX_ORDER:
        print(f"Error: order must be in {MIN_ORDER}..{MAX_ORDER}, "
              f"got {args.order}", file=sys.stderr)
        return 2
    if args.length < 1:
        print(f"Error: length must be at least 1, got {args.length}",
              file=sys.stderr)
        return 2

    try:
        text = load_corpus(args.corpus)
        tokens = tokenize(text)
        model = build_model(tokens, args.order)
    except MarkovError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    sample = generate_text(model, length=args.length, seed=args.seed)
    score = perplexity(model, tokens)

    if not args.quiet:
        print(BANNER)
        print(f"Corpus          : {len(tokens)} tokens, "
              f"{len(model.vocab)} distinct")
        print(f"Model           : order {model.order}, {model.states} states, "
              f"{model.transitions} transitions")
        print(f"Perplexity      : {score:.2f} bits/word")
        print("\nTop transitions:")
        for line in transition_report(model):
            print(line)
        print(f"\nSample (seed {args.seed}):")
        print("  " + detokenize(sample))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = to_dict(model, sample)
        payload["perplexity"] = score
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
