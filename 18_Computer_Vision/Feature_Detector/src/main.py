"""Command line entry point for the Feature Detector.

Usage
-----
    python src/main.py --demo                        # bundled samples
    python src/main.py --file photo.png              # Harris corners
    python src/main.py --file a.png --compare b.png --mode all
    python src/main.py --file a.png --threshold 5e-5 --json report.json

Fully offline: local images in, corner/keypoint statistics + ASCII preview
out. No network, no downloads (the bundled procedural samples ship in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from features import (
    DEFAULT_K,
    DEFAULT_THRESHOLD,
    MODES,
    FeatureError,
    analyse,
    bundle_samples,
    corner_mask,
    load_image,
    render_report,
    run_demo,
    to_dict,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("features")

BANNER = """
========================================
 FEATURE DETECTOR
   Harris corners from scratch
   + ORB keypoint matching, offline
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
        description="Detect Harris corners and match ORB keypoints offline")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="analyse the bundled procedural samples")
    mode.add_argument("--file", type=Path, default=None,
                      help="image (PNG/JPG) to analyse")
    parser.add_argument("--compare", type=Path, default=None,
                        help="second image for ORB matching")
    parser.add_argument("--mode", choices=MODES, default="harris",
                        help="detection mode (default harris)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Harris response threshold "
                             f"(default {DEFAULT_THRESHOLD:g})")
    parser.add_argument("--k", type=float, default=DEFAULT_K,
                        help=f"Harris k constant (default {DEFAULT_K:g})")
    parser.add_argument("--max-corners", type=int, default=200,
                        help="keep only the N strongest corners (default 200)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write detection statistics as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except FeatureError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.file is None:
        parser.error("one of the arguments --demo --file is required")

    # fast-fail: validate every flag BEFORE decoding any image
    if not 0.0 < args.k < 0.25:
        print(f"Error: k must be in (0, 0.25), got {args.k}",
              file=sys.stderr)
        return 2
    if args.threshold <= 0:
        print(f"Error: threshold must be positive, got {args.threshold}",
              file=sys.stderr)
        return 2
    if args.max_corners < 1:
        print(f"Error: max-corners must be positive, got {args.max_corners}",
              file=sys.stderr)
        return 2
    if args.mode in ("orb", "all") and args.compare is None:
        print("Error: orb mode needs --compare IMAGE", file=sys.stderr)
        return 2

    try:
        image = load_image(args.file)
        reference = load_image(args.compare) if args.compare else None
    except FeatureError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(render_report(args.mode, image, args.file.name,
                            threshold=args.threshold, k=args.k,
                            reference=reference))

    if args.json:
        payload = analyse(image, mode=args.mode, threshold=args.threshold,
                          k=args.k, max_corners=args.max_corners,
                          reference=reference)
        out = to_dict(args.mode, args.file.name, payload)
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(out, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
