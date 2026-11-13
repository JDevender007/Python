"""Command line entry point for the Image Segmentation project.

Usage
-----
    python src/main.py --demo                          # bundled samples
    python src/main.py --file photo.png --mode otsu    # one threshold
    python src/main.py --file photo.png --mode kmeans --clusters 5
    python src/main.py --file mask.png --mode components --connectivity 4
    python src/main.py --file photo.png --mode all --json report.json

Fully offline: local image in, segmentation statistics + ASCII preview
out. No network, no downloads (the bundled procedural samples ship in
data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from segmentation import (
    MAX_CLUSTERS,
    MIN_CLUSTERS,
    MODES,
    SegError,
    analyse,
    load_color_image,
    load_image,
    render_report,
    run_demo,
    to_dict,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("segmentation")

BANNER = """
========================================
 IMAGE SEGMENTATION
   Otsu + k-means + connected components
   from scratch, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Segment images offline (from-scratch Otsu, k-means "
                    "and connected components with cv2 cross-checks)")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="segment the bundled procedural samples")
    mode.add_argument("--file", type=Path, default=None,
                      help="image (PNG/JPG) to segment")
    parser.add_argument("--mode", choices=MODES, default="otsu",
                        help="segmentation mode (default otsu)")
    parser.add_argument("--clusters", type=int, default=4,
                        help=f"k-means cluster count "
                             f"({MIN_CLUSTERS}..{MAX_CLUSTERS}, default 4)")
    parser.add_argument("--connectivity", type=int, choices=(4, 8),
                        default=8, help="component connectivity (default 8)")
    parser.add_argument("--seed", type=int, default=42,
                        help="k-means seed (default 42)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write segmentation statistics as JSON")
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
        except SegError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.file is None:
        parser.error("one of the arguments --demo --file is required")

    # fast-fail: validate every flag BEFORE decoding the image
    if not MIN_CLUSTERS <= args.clusters <= MAX_CLUSTERS:
        print(f"Error: clusters must be in {MIN_CLUSTERS}..{MAX_CLUSTERS}, "
              f"got {args.clusters}", file=sys.stderr)
        return 2

    try:
        if args.mode in ("kmeans", "all"):
            image = load_color_image(args.file)
        else:
            image = load_image(args.file)
    except SegError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)

    if not args.quiet:
        print(render_report(args.mode, image, args.file.name,
                            clusters=args.clusters,
                            connectivity=args.connectivity,
                            seed=args.seed))

    if args.json:
        try:
            payload = analyse(image, mode=args.mode, clusters=args.clusters,
                              connectivity=args.connectivity,
                              seed=args.seed)
        except SegError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(to_dict(args.mode, args.file.name, payload),
                       indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
