"""Command line entry point for the Stock Market Analyzer.

Usage
-----
    python src/main.py --demo                          # bundled synthetic data
    python src/main.py --file stocks.csv               # your own OHLCV data
    python src/main.py --file stocks.csv --ticker ALPHA
    python src/main.py --file stocks.csv --window 50 --json report.json
    python src/main.py --file stocks.csv --chart chart.png

Fully offline: reads a local CSV and writes local files only. Synthetic
data — not investment advice.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from stock_analyzer import (
    MarketReport,
    StockError,
    analyze_market,
    analyze_ticker,
    load_prices,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("stock")

BANNER = """
========================================
 STOCK MARKET ANALYZER
   local OHLCV data, no market feeds
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyse a local OHLCV CSV (offline)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run the offline demo")
    source.add_argument("--file", type=Path, default=None, help="OHLCV CSV to analyse")
    parser.add_argument("--ticker", default=None,
                        help="analyse only this ticker")
    parser.add_argument("--window", type=int, default=20,
                        help="SMA window (default 20)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the report as JSON to this path")
    parser.add_argument("--chart", type=Path, default=None,
                        help="write a close-price chart PNG to this path")
    parser.add_argument("--quiet", action="store_true", help="suppress the text report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if args.window < 1:
        print("Error: --window must be >= 1", file=sys.stderr)
        return 2

    print(BANNER)
    try:
        frame = load_prices(args.file)
        if args.ticker:
            stats = analyze_ticker(frame, args.ticker, sma_window=args.window)
            report = MarketReport(tickers={stats.ticker: stats})
        else:
            report = analyze_market(frame, sma_window=args.window)
    except StockError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(report))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    if args.chart:
        try:
            _write_chart(frame, args.chart, args.ticker)
            print(f"Wrote {args.chart}")
        except StockError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    print("\nDone.")
    return 0


def _write_chart(frame, target: Path, ticker: str | None) -> None:
    """Save close prices (and SMA) as a PNG (matplotlib, Agg backend)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from stock_analyzer import sma
    except Exception as exc:  # pragma: no cover - matplotlib missing
        raise StockError(f"matplotlib unavailable: {exc}") from exc

    tickers = [ticker.upper()] if ticker else sorted(frame["ticker"].unique())
    target.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(11, 5))
    for symbol in tickers:
        subset = frame[frame["ticker"] == symbol].sort_values("date")
        closes = subset["close"].reset_index(drop=True)
        axis.plot(subset["date"], closes, linewidth=1.6, label=symbol)
        if len(closes) >= 20:
            axis.plot(subset["date"], sma(closes, 20), linewidth=1.0,
                      linestyle="--", alpha=0.7, label=f"{symbol} SMA20")
    axis.set_title("Close prices" + (f" - {ticker.upper()}" if ticker else ""))
    axis.set_ylabel("USD")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(target, dpi=100)
    plt.close(figure)


if __name__ == "__main__":
    raise SystemExit(main())
