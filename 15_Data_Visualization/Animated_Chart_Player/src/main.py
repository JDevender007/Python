"""Command line entry point for the Animated Chart Player.

Usage
-----
    python src/main.py --demo                      # all 3 GIFs from bundled data
    python src/main.py --file scores.csv --anim bar # one GIF
    python src/main.py --file scores.csv --list     # animation catalog
    python src/main.py --demo --out movies --fps 6

Fully offline: reads a local CSV and writes local GIFs (Agg + Pillow).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from player import (
    ANIMATIONS,
    DEFAULT_OUTPUT,
    DEMO_CSV,
    PlayerError,
    load_scores,
    render_animation,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("player")

BANNER = """
========================================
 ANIMATED CHART PLAYER
   matplotlib GIFs, fully offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render animated chart GIFs offline (Agg + Pillow)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="render every animation from the bundled sample")
    action.add_argument("--file", type=Path, default=None,
                        help="team-score CSV to animate")
    action.add_argument("--list", action="store_true",
                        help="list available animations")
    parser.add_argument("--anim", metavar="NAME", default=None,
                        help="render a single animation (default: all)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT,
                        help="output folder for GIFs")
    parser.add_argument("--fps", type=int, default=4,
                        help="frames per second in the GIF (1-30, default 4)")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress progress output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print(BANNER)
        for name, (_, description) in ANIMATIONS.items():
            print(f"  {name:<8} {description}")
        print(f"\n{len(ANIMATIONS)} animations available.")
        return 0

    if not 1 <= args.fps <= 30:
        print("Error: --fps must be in 1..30", file=sys.stderr)
        return 2

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            run_demo(out_dir=args.out, quiet=args.quiet)
        except PlayerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    # --file path
    if not args.quiet:
        print(BANNER)
    try:
        frame = load_scores(args.file)
    except PlayerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    names = [args.anim] if args.anim else list(ANIMATIONS)
    if args.anim and args.anim not in ANIMATIONS:
        print(f"Error: unknown animation {args.anim!r} "
              f"(available: {', '.join(sorted(ANIMATIONS))})", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"\nLoaded {len(frame)} rows; rendering {len(names)} "
              f"animation(s) at {args.fps} fps\n")

    for name in names:
        try:
            path = render_animation(name, frame,
                                    args.out / f"{name}.gif", fps=args.fps)
        except PlayerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"  {name:<8} -> {path} ({path.stat().st_size:,} bytes)")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
