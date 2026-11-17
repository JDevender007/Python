"""Command line entry point for the Edge Detector.

Usage
-----
    python src/main.py --demo                       # bundled samples, full report
    python src/main.py --file photo.png             # analyse your own image
    python src/main.py --file photo.png --method canny --low 60 --high 180
    python src/main.py --file photo.png --method all --json report.json

Fully offline: local image in, edge statistics + ASCII preview out. No
network, no downloads (the bundled procedural samples ship in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from edges import (
    ALL_METHODS,
    DEFAULT_HIGH,
    DEFAULT_LOW,
    DEFAULT_THRESHOLD,
    EdgeError,
    analyse,
    load_image,
    render_report,
    run_demo,
    to_dict,
    validate_thresholds,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("edges")

BANNER = """
========================================
 EDGE DETECTOR
   Sobel/Prewitt/Laplacian from scratch
   + cv2 Canny cross-check, offline
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
        description="Detect image edges offline (from-scratch convolutions "
                    "plus cv2 Canny cross-check)")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="analyse the bundled procedural samples")
    mode.add_argument("--file", type=Path, default=None,
                      help="image (PNG/JPG) to analyse")
    parser.add_argument("--method", choices=ALL_METHODS, default="sobel",
                        help="edge method (default sobel)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"gradient magnitude threshold "
                             f"(default {DEFAULT_THRESHOLD:g})")
    parser.add_argument("--low", type=float, default=DEFAULT_LOW,
                        help=f"Canny low hysteresis (default {DEFAULT_LOW:g})")
    parser.add_argument("--high", type=float, default=DEFAULT_HIGH,
                        help=f"Canny high hysteresis "
                             f"(default {DEFAULT_HIGH:g})")
    parser.add_argument("--json", type=Path, default=None,
                        help="write edge statistics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except EdgeError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.file is None:
        parser.error("one of the arguments --demo --file is required")

    # fast-fail: validate every flag BEFORE touching the image
    try:
        validate_thresholds(args.low, args.high, args.threshold)
    except EdgeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        image = load_image(args.file)
    except EdgeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)

    result = analyse(image, method=args.method, threshold=args.threshold,
                     low=args.low, high=args.high)

    if not args.quiet:
        print(render_report(result, image, args.file.name, args.method))

    if args.json:
        payload = to_dict(result, args.file.name, image.shape)
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
