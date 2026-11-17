"""Command line entry point for the Histogram Equalizer.

Usage
-----
    python src/main.py --demo                            # bundled samples
    python src/main.py --file photo.png                  # global CDF mapping
    python src/main.py --file photo.png --method clahe --clip 3.0 --tiles 8
    python src/main.py --file photo.png --out eq.png --json stats.json

Fully offline: local image in, equalized PNG + before/after stats out.
No network, no API keys, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from histogram import (
    METHODS,
    HistError,
    ascii_histogram,
    equalize,
    histogram_stats,
    load_image,
    render_report,
    run_demo,
    save_image,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("histogram")

BANNER = """
========================================
 HISTOGRAM EQUALIZER
   global CDF + CLAHE-style limiting
   from scratch with NumPy
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
        description="Equalise image histograms (global or CLAHE, offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled offline demo")
    parser.add_argument("--file", type=Path, default=None,
                        help="input image (PNG/JPEG, <= 512x512)")
    parser.add_argument("--method", choices=METHODS, default="global",
                        help="equalization method (default global)")
    parser.add_argument("--clip", type=float, default=2.0,
                        help="CLAHE clip limit (default 2.0)")
    parser.add_argument("--tiles", type=int, default=8,
                        help="CLAHE tile grid size (default 8; image sides "
                             "must be divisible by it)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the equalized image to this PNG path")
    parser.add_argument("--json", type=Path, default=None,
                        help="write before/after statistics as JSON")
    parser.add_argument("--ascii", action="store_true",
                        help="also print ASCII histograms of the result")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except HistError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.file is None:
        parser.error("one of the arguments --demo --file is required")

    # ---- fast-fail: validate flag inputs BEFORE loading/processing ------- #
    if not args.clip > 0 or args.clip != args.clip:
        print(f"Error: --clip must be > 0, got {args.clip}", file=sys.stderr)
        return 2
    if args.tiles < 2:
        print(f"Error: --tiles must be >= 2, got {args.tiles}",
              file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
    try:
        image = load_image(args.file)
        before = histogram_stats(image)
        processed = equalize(image, method=args.method,
                             clip_limit=args.clip, tiles=args.tiles)
        after = histogram_stats(processed)
    except HistError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        params = {"clip_limit": args.clip, "tiles": args.tiles}
        print(render_report(image, processed, args.method, params))
        if args.ascii:
            print("\nHistogram after:")
            print(ascii_histogram(processed))

    if args.out is not None:
        try:
            save_image(processed, args.out)
        except HistError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"\nWrote {args.out}")

    if args.json:
        payload = {
            "file": str(args.file),
            "method": args.method,
            "clip": args.clip if args.method == "clahe" else None,
            "tiles": args.tiles if args.method == "clahe" else None,
            "before": before,
            "after": after,
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
