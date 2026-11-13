"""Command line entry point for the Text Summarizer.

Usage
-----
    python src/main.py --demo                       # bundled articles
    python src/main.py --file articles.json         # summarize every article
    python src/main.py --file articles.json --index 1 --ratio 0.5
    python src/main.py --text "One sentence. Two sentences." --ratio 0.5
    python src/main.py --file articles.json --json out.json

Fully offline: local JSON/text in, ranked sentences + compression metrics
out. No network, no downloads (the bundled articles ship in data/).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from summarizer import (
    DEFAULT_ARTICLES,
    SummaryError,
    load_articles,
    render_report,
    run_demo,
    summarize,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("summarizer")

BANNER = """
========================================
 TEXT SUMMARIZER
   TF-IDF sentence ranking, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extractive TF-IDF text summarization (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="summarize the bundled articles")
    action.add_argument("--file", type=Path, default=None,
                        help="articles JSON file ([{title, text}, ...])")
    parser.add_argument("--text", default=None,
                        help="inline article text (not combinable with "
                             "--demo/--file)")
    parser.add_argument("--index", type=int, default=None,
                        help="summarize only this article index in --file")
    parser.add_argument("--ratio", type=float, default=0.4,
                        help="fraction of sentences to keep (default 0.4)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write summary metrics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- fast-fail validation of flag inputs, before any summarizing ------ #
    if not args.demo and args.file is None and args.text is None:
        parser.error("one of the arguments --demo --file --text is required")
    if args.text is not None and (args.demo or args.file is not None):
        parser.error("--text cannot be combined with --demo or --file")
    if args.demo and (args.index is not None or args.ratio != 0.4
                      or args.json is not None):
        parser.error("--index/--ratio/--json apply to --file or --text, "
                     "not --demo")
    if args.index is not None and args.text is not None:
        parser.error("--index requires --file, not --text")
    if not 0.0 < args.ratio <= 1.0:
        parser.error(f"--ratio must be in (0, 1], got {args.ratio}")
    if args.index is not None and args.index < 0:
        parser.error(f"--index must be >= 0, got {args.index}")
    if args.text is not None and not args.text.strip():
        parser.error("--text must not be empty")

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            run_demo()
        except SummaryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.quiet:
        print(BANNER)

    try:
        if args.text is not None:
            results = [summarize(args.text, ratio=args.ratio,
                                 title="Inline text")]
        else:
            articles = load_articles(args.file)
            if args.index is not None:
                if args.index >= len(articles):
                    raise SummaryError(
                        f"--index {args.index} out of range "
                        f"(file holds {len(articles)} articles)")
                articles = [articles[args.index]]
            results = [summarize(a["text"], ratio=args.ratio,
                                 title=a["title"]) for a in articles]
    except SummaryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        for result in results:
            print()
            print(render_report(result))

    if args.json:
        payload = results[0].to_dict() if len(results) == 1 \
            else [r.to_dict() for r in results]
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
