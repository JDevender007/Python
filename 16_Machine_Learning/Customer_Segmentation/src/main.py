"""Command line entry point for Customer Segmentation.

Usage
-----
    python src/main.py --demo                      # bundled data, full report
    python src/main.py --file customers.csv        # your own data (auto-k)
    python src/main.py --file customers.csv --k 4  # force 4 clusters
    python src/main.py --file customers.csv --json segments.json

Fully offline: local CSV in, cluster profiles out. No network, no downloads.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from segment import (
    DEMO_CSV,
    SegmentError,
    load_customers,
    render_report,
    run_demo,
    segment,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("segment")

BANNER = """
========================================
 CUSTOMER SEGMENTATION
   k-means + silhouette sweep, offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cluster customers with k-means (offline)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="cluster the bundled sample")
    action.add_argument("--file", type=Path, default=None,
                        help="customer CSV to cluster")
    parser.add_argument("--k", type=int, default=None,
                        help="force k clusters (default: best silhouette, 2..8)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write cluster profiles as JSON to this path")
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
            run_demo()
        except SegmentError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if not args.quiet:
        print(BANNER)
    try:
        frame = load_customers(args.file)
        result = segment(frame, k=args.k)
    except SegmentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result, frame))

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
