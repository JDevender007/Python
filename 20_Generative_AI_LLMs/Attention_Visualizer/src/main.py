"""Command line entry point for the Attention Visualizer.

Usage
-----
    python src/main.py --demo                     # bundled sentences
    python src/main.py --texts data/texts.json    # analyse every sentence
    python src/main.py --texts data/texts.json --sentence s1 --heads 6
    python src/main.py --demo --json run.json

Fully offline: local sentences in, attention statistics and ASCII heat
maps out. No network, no downloads (the sentences ship in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from attention import (
    DEFAULT_HEADS,
    AttentionError,
    analyse,
    ascii_heatmap,
    embed_tokens,
    load_texts,
    run_demo,
    to_dict,
    top_attended,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("attention")

BANNER = """
========================================
 ATTENTION VISUALIZER
   multi-head self-attention in NumPy
   entropy, diversity, ASCII heat maps
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
        description="Visualise multi-head self-attention over local text")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="run the offline demo on the bundled sentences")
    mode.add_argument("--texts", type=Path, default=None,
                      help="JSON file with a 'sentences' list")
    parser.add_argument("--sentence", default=None,
                        help="analyse only this sentence id")
    parser.add_argument("--heads", type=int, default=DEFAULT_HEADS,
                        help=f"attention heads (default {DEFAULT_HEADS})")
    parser.add_argument("--seed", type=int, default=0,
                        help="projection seed (default 0)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the summaries as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except AttentionError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.texts is None:
        parser.error("one of the arguments --demo --texts is required")

    # fast-fail: validate flags before reading the corpus
    if not 1 <= args.heads <= 16:
        print(f"Error: heads must be in 1..16, got {args.heads}",
              file=sys.stderr)
        return 2

    try:
        sentences = load_texts(args.texts)
        embeddings, vocab = embed_tokens(sentences)
    except AttentionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.sentence is not None:
        selected = [s for s in sentences if s.id == args.sentence]
        if not selected:
            print(f"Error: no sentence with id '{args.sentence}'",
                  file=sys.stderr)
            return 2
        sentences = selected

    try:
        summaries = [analyse(sentence, vocab, embeddings, n_heads=args.heads,
                             seed=args.seed) for sentence in sentences]
    except AttentionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(f"Vocabulary      : {len(vocab)} tokens, "
              f"embeddings {embeddings.shape[0]}x{embeddings.shape[1]}")
        print(f"Heads           : {args.heads}, seed {args.seed}")
        for summary in summaries:
            print(f"\n{summary['id']}  ({len(summary['tokens'])} tokens)")
            print("  " + " ".join(summary["tokens"]))
            print("  entropy  : " + ", ".join(
                f"{value:.2f}" for value in summary["entropy"]) + " bits")
            print(f"  diversity: {summary['diversity']:.3f}")
            row = min(2, len(summary["tokens"]) - 1)
            leaders = top_attended(summary["maps"][0], summary["tokens"],
                                   row=row, k=3)
            print(f"  top for '{summary['tokens'][row]}': " + ", ".join(
                f"{token} {weight:.2f}" for token, weight in leaders))
            for line in ascii_heatmap(summary["maps"][0]):
                print("  " + line)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "vocabulary": len(vocab),
            "heads": args.heads,
            "seed": args.seed,
            "sentences": [to_dict(summary) for summary in summaries],
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
