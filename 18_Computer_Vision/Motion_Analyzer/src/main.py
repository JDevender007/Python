"""Command line entry point for the Motion Analyzer.

Usage
-----
    python src/main.py --demo                      # bundled 20-frame sequence
    python src/main.py --frames data/frames        # analyse a folder
    python src/main.py --frames DIR --method diff --threshold 20 --json r.json

Fully offline: grayscale PNG frames in, motion masks + statistics + ASCII
overlays out. No network, no downloads (bundled data ships in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from motion import (
    DEFAULT_ALPHA,
    DEFAULT_THRESHOLD,
    DEFAULT_WARMUP,
    METHODS,
    MotionError,
    analyse,
    load_frames,
    render_report,
    run_demo,
    to_dict,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("motion")

BANNER = """
========================================
 MOTION ANALYZER
   frame differencing + background model
   from-scratch morphology, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect motion in a folder of grayscale frames offline")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="analyse the bundled 20-frame sequence")
    mode.add_argument("--frames", type=Path, default=None,
                      help="directory containing frame_*.png files")
    parser.add_argument("--method", choices=METHODS, default="all",
                        help="detector to run (default all)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"motion threshold (default {DEFAULT_THRESHOLD:g})")
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA,
                        help=f"background adapt rate (default {DEFAULT_ALPHA:g})")
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP,
                        help=f"frames used to learn the background "
                             f"(default {DEFAULT_WARMUP})")
    parser.add_argument("--json", type=Path, default=None,
                        help="write motion statistics as JSON")
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
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except MotionError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.frames is None:
        parser.error("one of the arguments --demo --frames is required")

    # fast-fail: validate every flag BEFORE decoding frames
    if not 0 < args.threshold < 255:
        print(f"Error: threshold must be in (0, 255), got {args.threshold}",
              file=sys.stderr)
        return 2
    if not 0 < args.alpha <= 1:
        print(f"Error: alpha must be in (0, 1], got {args.alpha}",
              file=sys.stderr)
        return 2
    if args.warmup < 1:
        print(f"Error: warmup must be at least 1, got {args.warmup}",
              file=sys.stderr)
        return 2

    try:
        frames = load_frames(args.frames)
    except MotionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(render_report(frames, args.method, args.threshold, args.alpha,
                            args.warmup))

    if args.json:
        try:
            payload = analyse(frames, args.method, args.threshold, args.alpha,
                              args.warmup)
        except MotionError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(to_dict(args.method, payload),
                                        indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
