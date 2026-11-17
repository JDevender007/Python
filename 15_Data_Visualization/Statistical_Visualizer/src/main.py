"""Command line entry point for the Statistical Visualizer.

Usage
-----
    python src/main.py --demo                      # bundled sample, all charts
    python src/main.py --file measurements.csv      # your own data
    python src/main.py --file data.csv --chart box # one chart to output/
    python src/main.py --file data.csv --json report.json
    python src/main.py --list                      # chart catalog

Fully offline: reads a local CSV, writes local PNGs (Agg backend).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from stats_viz import (
    CHART_TYPES,
    DEFAULT_OUTPUT,
    DEMO_CSV,
    StatsError,
    analyze,
    load_measurements,
    render_chart,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("stats")

BANNER = """
========================================
 STATISTICAL VISUALIZER
   offline stats + matplotlib (Agg)
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
        description="Descriptive statistics and statistical charts (offline)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="analyse the bundled sample and render all charts")
    action.add_argument("--file", type=Path, default=None,
                        help="measurements CSV to analyse")
    action.add_argument("--list", action="store_true",
                        help="list available chart types")
    parser.add_argument("--chart", metavar="NAME", default=None,
                        help="render a single chart type (with --file/--demo)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT,
                        help="output folder for PNGs")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the statistical report as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print(BANNER)
        for name, (_, description) in CHART_TYPES.items():
            print(f"  {name:<14} {description}")
        print(f"\n{len(CHART_TYPES)} chart types available.")
        return 0

    if args.demo:
        def demo() -> int:
            code = run_demo(out_dir=args.out, quiet=args.quiet)
            if args.json:
                payload = analyze(load_measurements(DEMO_CSV)).to_dict()
                args.json.parent.mkdir(parents=True, exist_ok=True)
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
                if not args.quiet:
                    print(f"\nWrote {args.json}")
            return code

        try:
            return _run_demo(args.quiet, demo)
        except StatsError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    # --file path
    if not args.quiet:
        print(BANNER)
    try:
        frame = load_measurements(args.file)
        report = analyze(frame)
    except StatsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(report))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2),
                             encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if args.chart:
        try:
            path = render_chart(args.chart, frame,
                                args.out / f"{args.chart}.png")
        except StatsError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"\nRendered {args.chart} -> {path} "
                  f"({path.stat().st_size:,} bytes)")
    elif not args.quiet:
        print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
