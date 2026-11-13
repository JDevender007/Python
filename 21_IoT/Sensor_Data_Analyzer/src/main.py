"""Command line entry point for the Sensor Data Analyzer.

Usage
-----
    python src/main.py --demo
    python src/main.py --readings data/readings.csv
    python src/main.py --readings data/readings.csv --z 2.5 --window 21
    python src/main.py --readings data/readings.csv --resample living_room:10min
    python src/main.py --readings data/readings.csv --json report.json

Fully offline: a local telemetry CSV in, an analysis report out. No
network, no database (the bundled readings ship in data/).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from analysis import (
    DEFAULT_WINDOW,
    DEFAULT_Z,
    METRIC,
    AnalysisError,
    correlation,
    detect_anomalies,
    detect_flatlines,
    detect_gaps,
    load_readings,
    render_report,
    resample_metric,
    run_demo,
    sensor_summary,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("analysis")

BANNER = """
========================================
 SENSOR DATA ANALYZER
   rolling z-scores, gaps, flatlines
   offline CSV in, report out
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyse a multi-sensor telemetry CSV")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="run the offline demo on the bundled data")
    mode.add_argument("--readings", type=Path, default=None,
                      help="telemetry CSV: timestamp,sensor,metric,value")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                        help=f"rolling window in samples "
                             f"(default {DEFAULT_WINDOW})")
    parser.add_argument("--z", type=float, default=DEFAULT_Z,
                        help=f"anomaly threshold in sigma (default {DEFAULT_Z})")
    parser.add_argument("--resample", default=None, metavar="SENSOR:RULE",
                        help="add a resampled view, e.g. living_room:10min")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the analysis as JSON")
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
        except AnalysisError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.readings is None:
        parser.error("one of the arguments --demo --readings is required")

    # fast-fail: validate flags before reading the CSV
    if args.window < 2:
        print(f"Error: window must be >= 2, got {args.window}",
              file=sys.stderr)
        return 2
    if not (args.z > 0):
        print(f"Error: z must be > 0, got {args.z}", file=sys.stderr)
        return 2
    resample_spec = None
    if args.resample is not None:
        parts = args.resample.split(":")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            print("Error: --resample expects SENSOR:RULE, "
                  "e.g. living_room:10min", file=sys.stderr)
            return 2
        resample_spec = (parts[0].strip(), parts[1].strip())

    try:
        frame = load_readings(args.readings)
        anomalies = detect_anomalies(frame, z=args.z, window=args.window)
        gaps = detect_gaps(frame)
        flatlines = detect_flatlines(frame)
        summary = sensor_summary(frame)
        corr = correlation(frame)
        table = None
        if resample_spec is not None:
            table = resample_metric(frame, resample_spec[0], METRIC,
                                    rule=resample_spec[1])
    except AnalysisError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(render_report(frame, anomalies, gaps, flatlines))
        if table is not None:
            print(f"\nResampled {resample_spec[0]} ({resample_spec[1]}):")
            print(table.to_string())
        print("\nCorrelation:")
        print(corr.to_string())

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rows": len(frame),
            "sensors": int(frame["sensor"].nunique()),
            "window": args.window,
            "z": args.z,
            "summary": summary.to_dict(orient="records"),
            "anomalies": [
                {"timestamp": str(row.timestamp), "sensor": str(row.sensor),
                 "value": float(row.value), "z_score": float(row.z_score)}
                for row in anomalies.itertuples()
            ],
            "gaps": [gap.to_dict() for gap in gaps],
            "flatlines": [
                {"sensor": run["sensor"], "length": run["length"],
                 "value": float(run["value"]), "start": str(run["start"])}
                for run in flatlines
            ],
            "correlation": {"sensors": list(corr.columns),
                            "matrix": corr.to_numpy().round(4).tolist()},
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
