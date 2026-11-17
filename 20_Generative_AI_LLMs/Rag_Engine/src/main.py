"""Command line entry point for the RAG Engine.

Usage
-----
    python src/main.py --demo                       # bundled document store
    python src/main.py --documents docs.jsonl       # build an index
    python src/main.py --query "how do I test code"
    python src/main.py --documents docs.jsonl --query "decorators" --top-k 5
    python src/main.py --demo --json run.json

Fully offline: a local JSONL document store in, ranked documents with an
extractive answer out. No network, no embedding API, no model downloads
(the bundled store ships in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from rag import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
    RagError,
    answer,
    build_index,
    evaluate,
    load_documents,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("rag")

BANNER = """
========================================
 RAG ENGINE
   hashed TF-IDF retrieval
   extractive answers + citations
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
        description="Answer questions over a local document store")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="run the offline demo on the bundled store")
    mode.add_argument("--documents", type=Path, default=None,
                      help="JSONL document store to index")
    parser.add_argument("--query", default=None,
                        help="question to answer against the store")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K,
                        help=f"documents to retrieve 1-{MAX_TOP_K} "
                             f"(default {DEFAULT_TOP_K})")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the result as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except RagError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.documents is None:
        parser.error("one of the arguments --demo --documents is required")

    # fast-fail: validate flags before reading or embedding anything
    if not 1 <= args.top_k <= MAX_TOP_K:
        print(f"Error: top_k must be in 1..{MAX_TOP_K}, got {args.top_k}",
              file=sys.stderr)
        return 2
    if args.query is None or not args.query.strip():
        print("Error: --query is required and must not be empty",
              file=sys.stderr)
        return 2

    try:
        documents = load_documents(args.documents)
        index = build_index(documents)
    except RagError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        result = answer(index, args.query, top_k=args.top_k)
    except RagError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(f"Documents       : {index.size} indexed, "
              f"{index.vocabulary} terms, dim {index.embedder.dim}")
        print(f"Query           : {result['query']}")
        print("\nRanked documents:")
        for position, hit in enumerate(result["hits"], start=1):
            print(f"  {position}. {hit['score']:+.4f}  "
                  f"{hit['id']:<16} {hit['title']}")
        if result["answer"]:
            print(f"\nAnswer          : {result['answer']}")
            print(f"Citations       : {', '.join(result['citations'])}")
        else:
            print("\nAnswer          : no document matches this query")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(result)
        payload["documents"] = index.size
        payload["vocabulary"] = index.vocabulary
        payload["evaluation"] = evaluate(index)["accuracy_at_1"]
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
