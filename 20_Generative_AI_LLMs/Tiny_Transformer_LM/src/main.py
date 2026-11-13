"""Command line entry point for the Tiny Transformer LM.

Usage
-----
    python src/main.py --demo                     # bundled corpus, sample text
    python src/main.py --file corpus.txt          # train on your own corpus
    python src/main.py --prompt "The " --length 200
    python src/main.py --file corpus.txt --prompt "A " --json out.json

Fully offline: local text in, training report + generated text out.
No network, no tokenizers, no pretrained weights (bundled corpus in data/).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path

from lm import (
    DEMO_CORPUS,
    LmError,
    CharTokenizer,
    load_corpus,
    render_report,
    run_demo,
    train_lm,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("main")

BANNER = """
========================================
 TINY TRANSFORMER LM
   character-level mini-GPT, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a miniature character-level Transformer "
                    "language model (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="train on the bundled corpus and sample text")
    action.add_argument("--file", type=Path, default=None,
                        help="UTF-8 corpus file to train on")
    parser.add_argument("--prompt", default=None,
                        help="seed text for generation (uses --file, or the "
                             "bundled corpus)")
    parser.add_argument("--steps", type=int, default=300,
                        help="training steps (default 300)")
    parser.add_argument("--length", type=int, default=200,
                        help="characters to generate (default 200)")
    parser.add_argument("--temperature", type=float, default=0.8,
                        help="sampling temperature (default 0.8)")
    parser.add_argument("--top-k", type=int, default=8,
                        help="top-k sampling cutoff (default 8)")
    parser.add_argument("--batch", type=int, default=32,
                        help="batch size (default 32)")
    parser.add_argument("--lr", type=float, default=3e-3,
                        help="AdamW learning rate (default 0.003)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed (default 42)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write metrics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the training report")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    """Fast-fail on bad flag values BEFORE any corpus load or training."""
    if args.steps < 1:
        raise LmError(f"steps must be >= 1, got {args.steps}")
    if args.length < 1:
        raise LmError(f"length must be >= 1, got {args.length}")
    if not math.isfinite(args.temperature) or args.temperature <= 0:
        raise LmError(f"temperature must be > 0, got {args.temperature}")
    if args.top_k < 1:
        raise LmError(f"top-k must be >= 1, got {args.top_k}")
    if args.batch < 1:
        raise LmError(f"batch must be >= 1, got {args.batch}")
    if not math.isfinite(args.lr) or args.lr <= 0:
        raise LmError(f"lr must be > 0, got {args.lr}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            run_demo()
        except LmError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.file is None and args.prompt is None:
        parser.error("one of the arguments --demo --file --prompt is required")

    try:
        _validate_args(args)
        source = args.file or DEMO_CORPUS
        text = load_corpus(source)
        tokenizer = CharTokenizer(text)
        if args.prompt is not None:
            tokenizer.encode(args.prompt)     # OOV check before training
    except LmError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
    try:
        result = train_lm(text, steps=args.steps, batch_size=args.batch,
                          lr=args.lr, seed=args.seed)
    except LmError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result))

    generated = None
    if args.prompt is not None:
        generated = result.sample(args.prompt, length=args.length,
                                  temperature=args.temperature,
                                  top_k=args.top_k, seed=args.seed)
        print(f"\nGenerated from prompt {args.prompt!r}:")
        for line in generated.splitlines():
            print(line)

    if args.json:
        payload = {"training": result.to_dict()}
        if generated is not None:
            payload["prompt"] = args.prompt
            payload["generated"] = generated
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
