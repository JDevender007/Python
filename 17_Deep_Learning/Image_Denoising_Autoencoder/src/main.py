"""Command line entry point for the Image Denoising Autoencoder.

Usage
-----
    python src/main.py --demo                       # bundled shapes, report
    python src/main.py --file shapes.csv            # train on your own CSV
    python src/main.py --file shapes.csv --epochs 60 --latent 48
    python src/main.py --file shapes.csv --denoise "0,0,0.4,..."
    python src/main.py --file shapes.csv --json metrics.json

Fully offline: local CSV in, denoising metrics + previews out. No network.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from autoencoder import (
    DEMO_CSV,
    NOISE_SIGMA,
    PIXELS,
    AError,
    ascii_image,
    load_images,
    render_report,
    run_demo,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("ae")

BANNER = """
========================================
 IMAGE DENOISING AUTOENCODER
   convolutional AE, offline
========================================
"""


def parse_pixels(text: str) -> list[float]:
    """Parse '0,0,0.4,...' (784 values, each 0..1) into a list."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    expected = len(PIXELS)
    if len(parts) != expected:
        raise AError(f"expected {expected} comma-separated pixel values, "
                     f"got {len(parts)}")
    values = []
    for i, part in enumerate(parts):
        try:
            number = float(part)
        except ValueError as exc:
            raise AError(f"not a number for image_{i}: {part!r}") from exc
        values.append(number)
    return values


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
        description="Denoise 28x28 shape images with a convolutional "
                    "autoencoder (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="train on the bundled shapes sample")
    action.add_argument("--file", type=Path, default=None,
                        help="image CSV (image_0..image_783,label) to train")
    parser.add_argument("--epochs", type=int, default=40,
                        help="training epochs (default 40)")
    parser.add_argument("--lr", type=float, default=5e-3,
                        help="Adam learning rate (default 0.005)")
    parser.add_argument("--batch", type=int, default=64,
                        help="mini-batch size (default 64)")
    parser.add_argument("--latent", type=int, default=32,
                        help="latent dimension (default 32)")
    parser.add_argument("--sigma", type=float, default=NOISE_SIGMA,
                        help=f"noise sigma (default {NOISE_SIGMA})")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed (default 42)")
    parser.add_argument("--denoise", metavar="PIXELS", default=None,
                        help="denoise one image: 784 comma-separated "
                             "values 0..1 (uses --file, or the bundled "
                             "sample)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write metrics as JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except AError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.file is None and args.denoise is None:
        parser.error("one of the arguments --demo --file --denoise "
                     "is required")

    # validate the pixel string up front so bad input fails fast
    pixels: list[float] | None = None
    if args.denoise is not None:
        try:
            pixels = parse_pixels(args.denoise)
        except AError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if not args.quiet:
        print(BANNER)
    try:
        # --denoise without --file trains on the bundled sample
        frame = load_images(args.file or DEMO_CSV)
        result = train_model(frame, epochs=args.epochs, lr=args.lr,
                             batch_size=args.batch, latent=args.latent,
                             sigma=args.sigma, seed=args.seed)
    except AError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result))

    if pixels is not None:
        try:
            reconstructed = result.denoise(pixels)
        except AError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print("\nDenoised preview (14x14):")
        for line in ascii_image(reconstructed).splitlines():
            print(f"  |{line}|")

    if args.json:
        payload = result.to_dict()
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
