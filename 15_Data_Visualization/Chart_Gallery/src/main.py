"""Command line entry point for the Chart Gallery.

Usage
-----
    python src/main.py --demo                     # render all 10 charts
    python src/main.py --list                     # list chart types
    python src/main.py --chart heatmap            # render one chart
    python src/main.py --chart bar --out graphs   # custom output folder
    python src/main.py --demo --manifest out.json # JSON manifest of files

Fully offline: reads the bundled CSV and writes local PNGs only (Agg
backend, no display needed).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from gallery import (
    CHART_TYPES,
    DEFAULT_OUTPUT,
    DEMO_CSV,
    GalleryError,
    list_charts,
    load_sample,
    render_chart,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("gallery")

BANNER = """
========================================
 CHART GALLERY
   offline matplotlib rendering (Agg)
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render chart types offline (Agg)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true", help="render every chart type")
    action.add_argument("--list", action="store_true", help="list available chart types")
    action.add_argument("--chart", metavar="NAME", help="render a single chart type")
    parser.add_argument("--file", type=Path, default=None,
                        help="data CSV (default: bundled sample)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT,
                        help="output folder for PNGs")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="write a JSON manifest of rendered files")
    parser.add_argument("--quiet", action="store_true", help="suppress progress output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print(BANNER)
        for name, description in list_charts():
            print(f"  {name:<14} {description}")
        print(f"\n{len(CHART_TYPES)} chart types available.")
        return 0

    if args.demo:
        try:
            run_demo(out_dir=args.out, quiet=args.quiet)
        except GalleryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if args.manifest:
            files = {name: str(args.out / f"{name}.png") for name in CHART_TYPES}
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(files, indent=2), encoding="utf-8")
            if not args.quiet:
                print(f"Wrote {args.manifest}")
        return 0

    # single chart
    if not args.quiet:
        print(BANNER)
    try:
        frame = load_sample(args.file) if args.file else load_sample(DEMO_CSV)
        target = args.out / f"{args.chart}.png"
        path = render_chart(args.chart, frame, target)
    except GalleryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"Rendered {args.chart} -> {path} ({path.stat().st_size:,} bytes)")
        print("\nDone.")
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps({args.chart: str(path)}, indent=2),
                                 encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
