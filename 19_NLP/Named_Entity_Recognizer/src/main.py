"""Command line entry point for the Named Entity Recognizer.

Usage
-----
    python src/main.py --demo                       # bundled sample + gold
    python src/main.py --text "Acme paid $4.5 million in Geneva on 2023-07-14."
    python src/main.py --file notes.txt             # annotate a text file
    python src/main.py --gold my_gold.json          # score against gold JSON
    python src/main.py --file notes.txt --json out.json

Fully offline: local text/JSON in, entity spans + precision/recall out.
No network, no downloads (gazetteers and gold ship in data/).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from ner import (
    NerError,
    evaluate,
    find_entities,
    load_gold,
    render_entities,
    render_evaluation,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("ner")

BANNER = """
========================================
 NAMED ENTITY RECOGNIZER
   Rules + gazetteers, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rule/pattern/gazetteer NER (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="annotate the bundled sample and score "
                             "against bundled gold")
    action.add_argument("--file", type=Path, default=None,
                        help="plain text file to annotate")
    action.add_argument("--text", default=None,
                        help="inline text to annotate")
    action.add_argument("--gold", type=Path, default=None,
                        help="gold annotation JSON to evaluate against")
    parser.add_argument("--json", type=Path, default=None,
                        help="write entities/metrics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- fast-fail validation of flag inputs, before any recognition ------ #
    if not (args.demo or args.file or args.text or args.gold):
        parser.error(
            "one of the arguments --demo --file --text --gold is required")
    if args.text is not None and not args.text.strip():
        parser.error("--text must not be empty")

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            run_demo()
        except NerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.quiet:
        print(BANNER)

    try:
        if args.gold is not None:
            annotations = load_gold(args.gold)
            predicted = [e for item in annotations
                         for e in find_entities(item["text"])]
            gold = [e for item in annotations for e in item["entities"]]
            result = evaluate(predicted, gold)
            if not args.quiet:
                print(render_evaluation(result))
            payload = result
        else:
            if args.text is not None:
                text = args.text
                title = "Inline text"
            else:
                if not args.file.is_file():
                    raise NerError(f"text file not found: {args.file}")
                text = args.file.read_text(encoding="utf-8")
                title = args.file.name
                if not text.strip():
                    raise NerError(f"no text in {args.file.name}")
            entities = find_entities(text)
            if not args.quiet:
                print(f"FILE: {title}")
                print()
                print(render_entities(text, entities))
            payload = {"file": title, "entities": [e.to_dict()
                                                   for e in entities]}
    except NerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
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
