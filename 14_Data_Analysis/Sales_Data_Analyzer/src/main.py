"""Command line entry point for the Sales Data Analyzer.

Usage
-----
    python src/main.py --demo                         # bundled sample CSV
    python src/main.py --file sales.csv               # your own data
    python src/main.py --file sales.csv --period Q --top 10
    python src/main.py --file sales.csv --segment product --json report.json
    python src/main.py --file sales.csv --chart chart.png

Fully offline: reads a local CSV and writes local files only.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sales_analyzer import (
    PERIODS,
    SalesError,
    analyze,
    load_sales,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("sales")

BANNER = """
========================================
 SALES DATA ANALYZER
   local CSV analysis, no network
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyse a local sales CSV (offline)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run the offline demo")
    source.add_argument("--file", type=Path, default=None, help="sales CSV to analyse")
    parser.add_argument("--period", default="M", choices=PERIODS,
                        help="time bucket: D/W/M/Q/Y (default M)")
    parser.add_argument("--segment", default=None, choices=("region", "category", "product"),
                        help="focus the breakdown on one segment")
    parser.add_argument("--top", type=int, default=5, help="top products to show")
    parser.add_argument("--chart", type=Path, default=None,
                        help="write a revenue trend PNG to this path")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the report as JSON to this path")
    parser.add_argument("--quiet", action="store_true", help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if args.top < 1:
        print("Error: --top must be >= 1", file=sys.stderr)
        return 2

    print(BANNER)
    try:
        frame = load_sales(args.file)
        report = analyze(frame, period=args.period)
    except SalesError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(report, top=args.top))

    if args.segment:
        print(f"\nDetailed {args.segment} breakdown:")
        table = report.by_segment[args.segment]
        for name, row in table.iterrows():
            print(f"  {str(name):<20} ${float(row['revenue']):>12,.2f}  "
                  f"{int(row['orders']):>5} orders  {int(row['units']):>6} units")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    if args.chart:
        try:
            _write_chart(report, args.chart)
            print(f"Wrote {args.chart}")
        except SalesError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    print("\nDone.")
    return 0


def _write_chart(report, target: Path) -> None:
    """Save the revenue trend as a PNG (matplotlib, Agg backend)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - matplotlib missing
        raise SalesError(f"matplotlib unavailable: {exc}") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.plot(report.by_period.index, report.by_period["revenue"],
              marker="o", linewidth=2, label="Revenue")
    if len(report.moving_average):
        axis.plot(report.moving_average.index, report.moving_average.values,
                  linewidth=2, linestyle="--", label=f"{report.period}-period MA")
    axis.set_title("Revenue trend")
    axis.set_ylabel("USD")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(target, dpi=100)
    plt.close(figure)


if __name__ == "__main__":
    raise SystemExit(main())
