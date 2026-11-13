"""Command line entry point for the Object Tracker.

Usage
-----
    python src/main.py --demo                     # bundled 24-frame sequence
    python src/main.py --frames data/frames       # track a folder of frames
    python src/main.py --frames DIR --colour red --json report.json

Fully offline: PNG frames in, trajectory statistics + ASCII map out.
No network, no downloads (the bundled sequence ships in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from tracker import (
    COLOUR_RANGES,
    MAX_JUMP,
    TrackerError,
    analyse,
    load_frames,
    position_errors,
    render_report,
    run_demo,
    to_dict,
    load_truth,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("tracker")

BANNER = """
========================================
 OBJECT TRACKER
   colour-blob centroids over frames
   nearest-neighbour association
========================================
"""

COLOURS = tuple(COLOUR_RANGES)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track colour blobs across a folder of PNG frames offline")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="track the bundled 24-frame sequence")
    mode.add_argument("--frames", type=Path, default=None,
                      help="directory containing frame_*.png files")
    parser.add_argument("--colour", choices=COLOURS + ("all",), default="all",
                        help="colour to track (default all)")
    parser.add_argument("--max-jump", type=float, default=MAX_JUMP,
                        help=f"reject centroid jumps above this many pixels "
                             f"(default {MAX_JUMP:g})")
    parser.add_argument("--json", type=Path, default=None,
                        help="write tracking statistics as JSON")
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
        except TrackerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.frames is None:
        parser.error("one of the arguments --demo --frames is required")

    # fast-fail: validate flags before decoding frames
    if args.max_jump <= 0:
        print(f"Error: max-jump must be positive, got {args.max_jump}",
              file=sys.stderr)
        return 2

    try:
        frames = load_frames(args.frames)
    except TrackerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    colours = COLOURS if args.colour == "all" else (args.colour,)
    if not args.quiet:
        print(BANNER)
        try:
            print(render_report(frames, colours))
        except TrackerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.json:
        try:
            result = analyse(frames, colours)
        except TrackerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        payload = to_dict(result)
        # optional ground-truth comparison when the CSV sits next to frames
        truth_path = Path(args.frames).parent / "truth.csv"
        if truth_path.is_file():
            try:
                truth = load_truth(Path(args.frames).parent)
                payload["errors"] = {
                    colour: position_errors(result["paths"][colour], truth,
                                            colour)
                    for colour in colours}
            except TrackerError:
                pass
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
