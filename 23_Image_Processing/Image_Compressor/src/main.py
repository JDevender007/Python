"""Command line entry point for the Image Compressor project.

Usage
-----
    python src/main.py --demo
    python src/main.py --quality 50
    python src/main.py --file data/photo_128.png --quality 90 --save out.png
    python src/main.py --sweep --json sweep.json

Fully offline: a local image in, a decoded PNG and statistics out.
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

from compressor import (
    PHOTO,
    QUALITIES,
    CodecError,
    check_quality,
    compress,
    decompress,
    load_image,
    mse,
    psnr,
    render_report,
    run_demo,
    save_image,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("compressor")

BANNER = """
========================================
 IMAGE COMPRESSOR
   DCT + quantise + RLE + Huffman
   offline, from scratch
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compress a greyscale image offline (JPEG-style codec)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled demo with self-checks")
    parser.add_argument("--file", type=Path, default=None,
                        help="input image (default: bundled photo_128.png)")
    parser.add_argument("--quality", type=int, default=75, metavar="1-100",
                        help="quantisation quality (default 75)")
    parser.add_argument("--sweep", action="store_true",
                        help="report every quality in the demo sweep")
    parser.add_argument("--save", type=Path, default=None,
                        help="write the decoded image to this PNG path")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the statistics as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def _print_row(row: dict) -> str:
    return (f"{row['quality']:>7}{row['tokens']:>9}"
            f"{row['distinct_tokens']:>9}{row['payload_bits']:>10}"
            f"{row['bits_per_pixel']:>8.2f}{row['total_bits_per_pixel']:>11.2f}"
            f"{row['psnr']:>9.2f}{row['max_error']:>9}")


TABLE_HEADER = (f"{'quality':>7}{'tokens':>9}{'symbols':>9}{'bits':>10}"
                f"{'bpp':>8}{'total bpp':>11}{'PSNR dB':>9}{'max err':>9}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if args.sweep or args.save is not None:
            parser.error("--demo does not accept --sweep or --save")
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except CodecError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    # fast-fail: validate flags before touching the filesystem
    try:
        quality = check_quality(args.quality)
    except CodecError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    source = args.file or PHOTO
    try:
        image = load_image(source)
    except CodecError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(f"Image: {source.name} {image.shape[1]}x{image.shape[0]} "
              f"greyscale ({image.size} px, {image.size * 8 / 8:.0f} bytes "
              f"raw)")

    rows = []
    try:
        if args.sweep:
            rows = [render_report(image, level) for level in QUALITIES]
        else:
            rows = [render_report(image, quality)]
    except CodecError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print()
        print(TABLE_HEADER)
        print("-" * len(TABLE_HEADER))
        for row in rows:
            print(_print_row(row))

    if args.save is not None:
        try:
            compressed = compress(image, quality)
            rebuilt = decompress(compressed)
            save_image(rebuilt, args.save)
        except CodecError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"\nWrote {args.save} "
                  f"(PSNR {psnr(image, rebuilt):.2f} dB, "
                  f"MSE {mse(image, rebuilt):.2f})")

    if args.json:
        payload = {
            "file": str(source),
            "image_shape": list(image.shape),
            "pixels": image.size,
            "rows": rows,
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
