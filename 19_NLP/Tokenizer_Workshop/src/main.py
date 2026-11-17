"""Command line entry point for the Tokenizer Workshop.

Usage
-----
    python src/main.py --demo                       # bundled corpus
    python src/main.py --file notes.txt             # tokenize your own file
    python src/main.py --text "The cats are running"
    python src/main.py --text "..." --n 3 --no-stopwords --json out.json

Fully offline: local text in, tokens/stems/n-grams/stats out. No network,
no downloads (the bundled corpus and stopwords ship in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from tokenizer import (
    TokenError,
    load_corpus,
    load_stopwords,
    process,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("tokenizer")

BANNER = """
========================================
 TOKENIZER WORKSHOP
   Regex tokens, stems, n-grams, offline
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
        description="Regex tokenization, stemming and n-grams (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run the bundled corpus pipeline")
    action.add_argument("--file", type=Path, default=None,
                        help="text file to tokenize")
    parser.add_argument("--text", default=None,
                        help="inline text to tokenize (not combinable "
                             "with --demo/--file)")
    parser.add_argument("--n", type=int, default=2,
                        help="n-gram size (default 2)")
    parser.add_argument("--min-length", type=int, default=1,
                        help="drop tokens shorter than this (default 1)")
    parser.add_argument("--no-stopwords", action="store_true",
                        help="keep stopword tokens in the pipeline")
    parser.add_argument("--drop-numbers", action="store_true",
                        help="drop pure-digit tokens")
    parser.add_argument("--top", type=int, default=8,
                        help="how many top tokens to report (default 8)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write pipeline metrics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- fast-fail validation of flag inputs, before any pipeline work ---- #
    if not args.demo and args.file is None and args.text is None:
        parser.error("one of the arguments --demo --file --text is required")
    if args.text is not None and (args.demo or args.file is not None):
        parser.error("--text cannot be combined with --demo or --file")
    if args.n < 1:
        parser.error(f"--n must be >= 1, got {args.n}")
    if args.min_length < 1:
        parser.error(f"--min-length must be >= 1, got {args.min_length}")
    if args.top < 1:
        parser.error(f"--top must be >= 1, got {args.top}")
    if args.text is not None and not args.text.strip():
        parser.error("--text must not be empty")

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except TokenError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if not args.quiet:
        print(BANNER)

    try:
        # --text needs a stopword list too; --file may carry its own corpus
        text = args.text if args.text is not None \
            else load_corpus(args.file)
        result = process(
            text,
            n=args.n,
            use_stopwords=not args.no_stopwords,
            min_length=args.min_length,
            keep_numbers=not args.drop_numbers,
            top=args.top,
        )
    except TokenError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result.to_dict(), indent=2),
                             encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
