"""Command line entry point for the Morphological Processing project.

Usage
-----
    python src/main.py --demo
    python src/main.py --op clean --components
    python src/main.py --op open --op close --shape disk --radius 2
    python src/main.py --op boundary --save out.png --json run.json --quiet

Fully offline: a local image in, a mask PNG + statistics out.
No network, no API keys, no OpenCV, no SciPy, no skimage.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

from morph import (
    BORDER_MODES,
    NOISY,
    OPERATIONS,
    SE_SHAPES,
    MorphError,
    apply_operation,
    area,
    ascii_thumb,
    describe_se,
    fraction,
    label_components,
    largest_components,
    load_image,
    render_report,
    run_demo,
    save_image,
    skeleton,
    structuring_element,
    threshold,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("morph")

BANNER = """
========================================
 MORPHOLOGICAL PROCESSING
   erode, dilate, open, close
   components + thinning, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Binary morphology on a local image, offline")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled demo with self-checks")
    parser.add_argument("--file", type=Path, default=None,
                        help="input image (default: bundled noisy_shapes_128.png)")
    parser.add_argument("--threshold", type=int, default=128, metavar="0-255",
                        help="binarisation level, pixels above it are "
                             "foreground (default 128)")
    parser.add_argument("--shape", default="square", choices=SE_SHAPES,
                        help="structuring element shape (default square)")
    parser.add_argument("--size", type=int, default=3,
                        help="odd side length for square/cross elements "
                             "(default 3)")
    parser.add_argument("--radius", type=int, default=1,
                        help="radius for disk/diamond elements (default 1)")
    parser.add_argument("--op", action="append", choices=OPERATIONS,
                        default=None,
                        help="operation to apply, repeatable and applied in "
                             "order (default: clean)")
    parser.add_argument("--skeleton", action="store_true",
                        help="also thin the result (Zhang-Suen)")
    parser.add_argument("--components", action="store_true",
                        help="also list the connected components")
    parser.add_argument("--ascii", action="store_true",
                        help="print an ASCII preview of the result")
    parser.add_argument("--save", type=Path, default=None,
                        help="write the resulting mask as a PNG")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the run summary as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def _check_flags(parser: argparse.ArgumentParser, args) -> None:
    if args.demo:
        if (args.op or args.skeleton or args.components or args.ascii
                or args.save is not None or args.json is not None):
            parser.error("--demo does not accept --op, --skeleton, "
                         "--components, --ascii, --save or --json")
    if not 0 <= args.threshold <= 255:
        parser.error(f"--threshold must be in [0, 255], got {args.threshold}")
    if args.shape in ("square", "cross") and args.size % 2 == 0:
        parser.error(f"--size must be odd for a {args.shape} element, "
                     f"got {args.size}")
    if args.size < 1:
        parser.error(f"--size must be >= 1, got {args.size}")
    if args.radius < 0:
        parser.error(f"--radius must be >= 0, got {args.radius}")


def _payload(mask, stages, element, args, operations, thin) -> dict[str, Any]:
    _, components = label_components(mask, 8)
    payload: dict[str, Any] = {
        "file": str(args.file or NOISY),
        "threshold": args.threshold,
        "element": {"shape": args.shape, "size": args.size,
                    "radius": args.radius,
                    "description": describe_se(element)},
        "operations": list(operations),
        "stages": stages,
        "final_pixels": area(mask),
        "final_share": round(fraction(mask), 6),
        "components": [component.to_dict() for component in components],
    }
    if thin is not None:
        _, skeleton_components = label_components(thin, 8)
        payload["skeleton"] = {
            "pixels": area(thin),
            "components": len(skeleton_components),
            "share_of_result": round(area(thin) / max(1, area(mask)), 6),
        }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _check_flags(parser, args)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except MorphError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.quiet:
        print(BANNER)

    try:
        element = structuring_element(args.shape, size=args.size,
                                      radius=args.radius)
        image = load_image(args.file or NOISY)
        mask = threshold(image, args.threshold)
    except MorphError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    operations = args.op or ["clean"]
    stages: list[dict[str, Any]] = []
    input_area = area(mask)
    current = mask
    try:
        stages.append({
            "operation": "input",
            "pixels": input_area,
            "share": fraction(mask),
            "delta": 0,
            "components": len(label_components(mask, 8)[1]),
        })
        for name in operations:
            current = apply_operation(current, name, element)
            stages.append({
                "operation": name,
                "pixels": area(current),
                "share": fraction(current),
                "delta": area(current) - input_area,
                "components": len(label_components(current, 8)[1]),
            })
        thin = skeleton(current) if args.skeleton else None
    except MorphError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        source_name = (args.file or NOISY).name
        print(f"\nImage  : {source_name} {image.shape[1]}x{image.shape[0]}, "
              f"{len(np.unique(image))} grey level(s)")
        print(f"Mask   : pixels above {args.threshold}")
        print(f"Element: {args.shape}, {describe_se(element)}")
        print()
        print(render_report(stages, "OPERATIONS - applied in order"))

        if args.components:
            big = largest_components(current, 20, 8)
            print(f"\nComponents (8-connectivity, area >= 20): {len(big)}")
            header = (f"  {'label':>6}{'area':>8}{'height':>8}{'width':>7}"
                      f"{'row':>9}{'col':>9}{'border':>8}")
            print(header)
            print("  " + "-" * (len(header) - 2))
            for component in big:
                print(f"  {component.label:>6}{component.area:>8}"
                      f"{component.height:>8}{component.width:>7}"
                      f"{component.centroid[0]:>9.1f}"
                      f"{component.centroid[1]:>9.1f}"
                      f"{str(component.touches_border):>8}")

        if thin is not None:
            print(f"\nSkeleton: {area(thin)} px "
                  f"({100.0 * area(thin) / max(1, area(current)):.2f}% of the "
                  f"result), "
                  f"{len(label_components(thin, 8)[1])} part(s)")

        if args.ascii:
            print("\nASCII preview")
            print(ascii_thumb(current, 64))

    if args.save is not None:
        try:
            save_image(current, args.save)
        except MorphError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"\nWrote {args.save}")

    if args.json is not None:
        payload = _payload(current, stages, element, args, operations, thin)
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
