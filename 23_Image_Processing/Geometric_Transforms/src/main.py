"""Command line entry point for Geometric Transforms.

Usage
-----
    python src/main.py --demo                              # bundled samples
    python src/main.py --file img.png --rotate 30          # rotate 30 deg
    python src/main.py --file img.png --scale 1.5 --edges wrap
    python src/main.py --file img.png --translate "10,-5" --interp nearest
    python src/main.py --file img.png --rotate 45 --out rot.png --json s.json

Fully offline: local image in, transformed PNG + stats out.
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

from geometry import (
    EDGE_MODES,
    INTERPOLATIONS,
    GeoError,
    affine_warp,
    compose,
    image_center,
    image_stats,
    load_image,
    psnr,
    rotation_matrix,
    run_demo,
    save_image,
    scaling_matrix,
    translation_matrix,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("geometry")

BANNER = """
========================================
 GEOMETRIC TRANSFORMS
   inverse mapping + bilinear
   interpolation from scratch
========================================
"""


def parse_translate(text: str) -> tuple[float, float]:
    """Parse 'dx,dy' into a translation tuple."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(
            f"expected 'dx,dy' (two comma-separated numbers), got {text!r}")
    try:
        dx, dy = float(parts[0]), float(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"not a number in 'dx,dy': {text!r}") from exc
    if not (dx == dx) or not (dy == dy):          # NaN check
        raise argparse.ArgumentTypeError(
            f"translation must be finite, got {text!r}")
    return dx, dy


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
        description="Rotate/scale/translate/affine-warp an image (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled offline demo")
    parser.add_argument("--file", type=Path, default=None,
                        help="input image (PNG/JPEG, <= 512x512)")
    parser.add_argument("--rotate", type=float, default=None, metavar="DEG",
                        help="rotate content by DEG degrees (counter-"
                             "clockwise as displayed)")
    parser.add_argument("--scale", type=float, default=None, metavar="F",
                        help="zoom content by factor F about the centre")
    parser.add_argument("--translate", type=parse_translate, default=None,
                        metavar="DX,DY",
                        help="shift content by DX,DY pixels")
    parser.add_argument("--interp", choices=INTERPOLATIONS, default="bilinear",
                        help="interpolation (default bilinear)")
    parser.add_argument("--edges", choices=EDGE_MODES, default="reflect",
                        help="out-of-bounds fill mode (default reflect)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the transformed image to this PNG path")
    parser.add_argument("--json", type=Path, default=None,
                        help="write transform statistics as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except GeoError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.file is None:
        parser.error("one of the arguments --demo --file is required")
    if args.rotate is None and args.scale is None \
            and args.translate is None:
        parser.error("one of the arguments --rotate --scale --translate "
                     "is required with --file")

    # ---- fast-fail: validate numeric flags BEFORE loading/processing ------ #
    if args.rotate is not None and args.rotate != args.rotate:
        print(f"Error: --rotate must be a finite number, got {args.rotate}",
              file=sys.stderr)
        return 2
    if args.scale is not None and (not (args.scale > 0)
                                   or args.scale != args.scale):
        print(f"Error: --scale must be > 0, got {args.scale}",
              file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
    try:
        image = load_image(args.file)
        # content pipeline: scale first, then rotate, then translate
        pieces = []
        if args.scale is not None:
            pieces.append(scaling_matrix(args.scale, image_center(image)))
        if args.rotate is not None:
            pieces.append(rotation_matrix(args.rotate, image_center(image)))
        if args.translate is not None:
            pieces.append(translation_matrix(*args.translate))
        matrix = compose(*pieces)
        transformed = affine_warp(image, matrix, order=args.interp,
                                  mode=args.edges)
        stats = image_stats(transformed)
        original_psnr = psnr(image, transformed)
    except GeoError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        label = " ".join(
            part for part in (
                f"rotate {args.rotate:g}" if args.rotate is not None else "",
                f"scale {args.scale:g}" if args.scale is not None else "",
                f"translate {args.translate}" if args.translate else "",
            ) if part)
        print(f"Transformed {args.file.name} "
              f"({image.shape[0]}x{image.shape[1]}) by {label}")
        print(f"  interp={args.interp}  edges={args.edges}")
        print(f"  mean {stats['mean']}  std {stats['std']}  "
              f"range {stats['min']}..{stats['max']}")
        print(f"  PSNR vs original {original_psnr:.2f} dB")

    if args.out is not None:
        try:
            save_image(transformed, args.out)
        except GeoError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"Wrote {args.out}")

    if args.json:
        payload = {
            "file": str(args.file),
            "rotate": args.rotate,
            "scale": args.scale,
            "translate": list(args.translate) if args.translate else None,
            "interp": args.interp,
            "edges": args.edges,
            "psnr_vs_original": round(original_psnr, 3),
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
