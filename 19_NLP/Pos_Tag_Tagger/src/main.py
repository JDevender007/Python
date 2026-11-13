"""Command line entry point for the Pos Tag Tagger.

Usage
-----
    python src/main.py --demo                        # bundled corpus
    python src/main.py --file corpus.txt             # train/eval on your corpus
    python src/main.py --sentence "Where does the dog sleep"
    python src/main.py --file corpus.txt --ratio 0.9 --json metrics.json

Fully offline: local CoNLL corpus in (word<TAB>tag lines), accuracy and
tagged sentences out. No network, no downloads (the corpus ships in data/).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from hmm_tagger import (
    DEFAULT_CORPUS,
    TaggerError,
    baseline_accuracy,
    corpus_stats,
    evaluate,
    load_corpus,
    render_report,
    run_demo,
    split_corpus,
    train_hmm,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("pos_tagger")

BANNER = """
========================================
 POS TAG Tagger
   Bigram HMM + Viterbi, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bigram HMM POS tagger with Viterbi decoding (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="train/evaluate on the bundled corpus")
    action.add_argument("--file", type=Path, default=None,
                        help="CoNLL-style tagged corpus (word<TAB>tag)")
    parser.add_argument("--sentence", metavar="TEXT", default=None,
                        help="tag this raw sentence (uses --file, or the "
                             "bundled corpus)")
    parser.add_argument("--ratio", type=float, default=0.8,
                        help="fraction of sentences used for training "
                             "(default 0.8)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write metrics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- fast-fail validation of flag inputs, before any training --------- #
    if not args.demo and args.file is None and args.sentence is None:
        parser.error(
            "one of the arguments --demo --file --sentence is required")
    if args.demo and args.sentence is not None:
        parser.error("--sentence cannot be combined with --demo")
    if not 0.0 < args.ratio < 1.0:
        parser.error(f"--ratio must be in (0, 1), got {args.ratio}")
    sentence_words: list[str] = []
    if args.sentence is not None:
        sentence_words = args.sentence.split()
        if not sentence_words:
            parser.error("--sentence must not be empty")

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            run_demo()
        except TaggerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.quiet:
        print(BANNER)

    try:
        sentences = load_corpus(args.file or DEFAULT_CORPUS)
        stats = corpus_stats(sentences)
        train, test = split_corpus(sentences, args.ratio)
        model = train_hmm(train)
        result = evaluate(model, test)
        baseline = baseline_accuracy(model, test)
        sample = model.tag_text(" ".join(sentence_words)) \
            if sentence_words else None
    except TaggerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(stats, (len(train), len(test)), baseline,
                            result, sample or []))

    if sample:
        print("\nTagged: " + "  ".join(f"{w}/{t}" for w, t in sample))

    if args.json:
        payload = {
            "sentences": stats["sentences"],
            "tokens": stats["tokens"],
            "train": len(train),
            "test": len(test),
            "ratio": args.ratio,
            "baseline_accuracy": round(baseline, 4),
            "hmm_accuracy": round(result["accuracy"], 4),
            "per_tag": result["tags"],
        }
        if sample:
            payload["tagged"] = [{"word": w, "tag": t} for w, t in sample]
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2),
                             encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
