"""Command line entry point for the Log Monitor.

Usage
-----
    python src/main.py --demo                              # bundled logs
    python src/main.py --file data/app.log                 # analyse one file
    python src/main.py --file data/app.log --threshold 0.4 --top 3
    python src/main.py --file data/app.log --json report.json

Fully offline: local log files in, aggregated report out. No network,
no log shippers, no daemons (the bundled samples ship in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from logmonitor import (
    LogError,
    error_rate,
    parse_file,
    render_report,
    run_demo,
    summarize,
    threshold_alerts,
    top_offenders,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("logmonitor")

BANNER = """
========================================
 LOG MONITOR
   offline log parsing + alerting
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse logs, aggregate error rates, and raise alerts "
                    "(offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="analyse the bundled app.log + legacy.log")
    action.add_argument("--file", type=Path, default=None,
                        help="log file to analyse")
    parser.add_argument("--threshold", type=float, default=0.2,
                        help="error-rate alert threshold 0..1 (default 0.2)")
    parser.add_argument("--min-samples", type=int, default=1,
                        help="minimum records before a service can alert "
                             "(default 1)")
    parser.add_argument("--top", type=int, default=5,
                        help="number of top offenders to show (default 5)")
    parser.add_argument("--lenient", action="store_true",
                        help="skip malformed lines instead of failing")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the aggregated report as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def _validate(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Fast-fail flag validation before any file is read."""
    if not 0.0 <= args.threshold <= 1.0:
        parser.error(f"--threshold must be in 0..1, got {args.threshold}")
    if args.min_samples < 1:
        parser.error(f"--min-samples must be >= 1, got {args.min_samples}")
    if args.top < 1:
        parser.error(f"--top must be >= 1, got {args.top}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate(parser, args)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except LogError as exc:
            # --demo never fails on user input (rule): bundled data is part
            # of the repo, so a LogError here is reported but not fatal.
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    if args.file is None:
        parser.error("one of the arguments --demo --file is required")

    if not args.quiet:
        print(BANNER)
    try:
        records, skipped = parse_file(args.file, strict=not args.lenient)
        summaries = summarize(records)
        alerts = threshold_alerts(summaries, args.threshold, args.min_samples)
        top = top_offenders(summaries, args.top)
    except LogError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(records, summaries, alerts, top,
                            args.threshold, args.min_samples, skipped))
        print("\nDone.")

    if args.json:
        payload = {
            "source": str(args.file),
            "records": len(records),
            "skipped": skipped,
            "error_rate": round(error_rate(records), 4),
            "threshold": args.threshold,
            "min_samples": args.min_samples,
            "services": [s.to_dict() for s in summaries.values()],
            "alerts": [s.service for s in alerts],
            "top_offenders": [s.service for s in top],
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
