"""Command line entry point for the Report Generator.

Usage
-----
    python src/main.py --demo                       # bundled data -> output/
    python src/main.py --file data.csv              # your own data
    python src/main.py --file data.csv --title "Q4 Review"
    python src/main.py --file data.csv --out reports/ --json summary.json
    python src/main.py --file data.csv --format md  # markdown only

Fully offline: reads a local CSV, writes local HTML/Markdown (charts are
base64-embedded PNGs — no CDN, no network).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from report import (
    DEFAULT_OUTPUT,
    DEMO_CSV,
    DEMO_TITLE,
    ReportError,
    build_report,
    load_data,
    run_demo,
    save_report,
    summarize,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("report")

BANNER = """
========================================
 REPORT GENERATOR
   HTML + Markdown, fully offline
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate offline HTML/Markdown reports from a CSV")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="report from the bundled sample")
    action.add_argument("--file", type=Path, default=None,
                        help="performance CSV to report on")
    parser.add_argument("--title", default=DEMO_TITLE,
                        help="report title")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT,
                        help="output folder for report.html / report.md")
    parser.add_argument("--format", choices=("both", "html", "md"),
                        default="both", help="which formats to write")
    parser.add_argument("--json", type=Path, default=None,
                        help="also write the summary numbers as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            run_demo(out_dir=args.out, quiet=args.quiet)
        except ReportError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            summary = summarize(load_data(DEMO_CSV))
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(summary.to_dict(), indent=2),
                                 encoding="utf-8")
            if not args.quiet:
                print(f"Wrote {args.json}")
        return 0

    # --file path
    if not args.quiet:
        print(BANNER)
    try:
        frame = load_data(args.file)
    except ReportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    summary = summarize(frame)
    if not args.quiet:
        print(f"\nLoaded {len(frame)} rows; revenue "
              f"${summary.totals['revenue']:,.0f} "
              f"(margin {summary.totals['margin_pct']:.1f}%)")
        print("\nInsights:")
        for note in summary.notes:
            print(f"  - {note}")

    document, markdown = build_report(frame, args.title)
    args.out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        if args.format in ("both", "html"):
            html_path = args.out / "report.html"
            html_path.write_text(document, encoding="utf-8")
            if html_path.stat().st_size < 50_000:
                raise ReportError(f"HTML report too small: {html_path}")
            written.append(html_path)
        if args.format in ("both", "md"):
            md_path = args.out / "report.md"
            md_path.write_text(markdown, encoding="utf-8")
            if md_path.stat().st_size == 0:
                raise ReportError(f"Markdown report empty: {md_path}")
            written.append(md_path)
    except ReportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(summary.to_dict(), indent=2),
                             encoding="utf-8")
        written.append(args.json)

    if not args.quiet:
        for path in written:
            print(f"Wrote {path} ({path.stat().st_size:,} bytes)")
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
