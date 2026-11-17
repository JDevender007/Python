"""Command line entry point for Convolution Filters.

Usage
-----
    python src/main.py --demo                             # bundled images
    python src/main.py --file img.png --filter gaussian   # one filter pass
    python src/main.py --file img.png --filter box --size 5 --edges wrap
    python src/main.py --file img.png --filter sharpen --out out.png
    python src/main.py --file img.png --filter emboss --json stats.json

Fully offline: local image in, filtered PNG + stats out. No network,
no API keys, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from filters import (
    DEMO_IMG,
    EDGE_MODES,
    FILTER_NAMES,
    ImgError,
    apply_filter,
    filter_report,
    load_image,
    run_demo,
    save_image,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("filters")

BANNER = """
========================================
 CONVOLUTION FILTERS
   box/gaussian/sharpen/emboss from
   scratch with NumPy only
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
        description="Apply classic convolution filters to an image (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled offline demo")
    parser.add_argument("--file", type=Path, default=None,
                        help="input image (PNG/JPEG, <= 512x512)")
    parser.add_argument("--filter", choices=FILTER_NAMES, default="gaussian",
                        help="filter to apply (default gaussian)")
    parser.add_argument("--size", type=int, default=None,
                        help="odd kernel size for box/gaussian (default: "
                             "box 3, gaussian = 3*sigma)")
    parser.add_argument("--sigma", type=float, default=1.5,
                        help="gaussian sigma (default 1.5)")
    parser.add_argument("--edges", choices=EDGE_MODES, default="reflect",
                        help="edge padding mode (default reflect)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the filtered image to this PNG path")
    parser.add_argument("--json", type=Path, default=None,
                        help="write filter statistics as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except ImgError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.file is None:
        parser.error("one of the arguments --demo --file is required")

    # ---- fast-fail: validate flag inputs BEFORE loading/processing ------- #
    if args.filter in ("box", "gaussian") and args.size is not None \
            and args.size < 1:
        print(f"Error: --size must be >= 1, got {args.size}",
              file=sys.stderr)
        return 2
    if args.filter == "gaussian" and (not args.sigma or args.sigma <= 0
                                      or args.sigma != args.sigma):
        print(f"Error: --sigma must be > 0, got {args.sigma}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
    try:
        image = load_image(args.file)
        params: dict[str, object] = {}
        if args.size is not None:
            params["size"] = args.size
        if args.filter == "gaussian":
            params["sigma"] = args.sigma
        filtered = apply_filter(image, args.filter, mode=args.edges, **params)
        stats = filter_report(image, filtered)
    except ImgError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"Filtered {args.file.name}: {image.shape[0]}x{image.shape[1]} "
              f"grey with {args.filter} (edges={args.edges})")
        print(f"  mean {stats['mean']}  std {stats['std']}  "
              f"range {stats['min']}..{stats['max']}")
        print(f"  MSE vs original {stats['mse']}  "
              f"PSNR {stats['psnr_db']} dB")

    if args.out is not None:
        try:
            save_image(filtered, args.out)
        except ImgError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"Wrote {args.out}")

    if args.json:
        payload = {
            "file": str(args.file),
            "filter": args.filter,
            "edges": args.edges,
            "size": args.size,
            "sigma": args.sigma if args.filter == "gaussian" else None,
            **stats,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
