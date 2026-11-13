"""Command line entry point for the Network Monitor.

Usage
-----
    python src/main.py --demo               # one snapshot, offline-friendly
    python src/main.py --watch --interval 2 # refresh every 2 seconds
    python src/main.py --csv out.csv        # write a snapshot to CSV
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

from monitor import format_snapshot, reset_counters, take_snapshot

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("netmon")

BANNER = """
========================================
 NETWORK MONITOR
========================================
"""


def write_csv(snapshot, path: Path) -> Path:
    """Export the interface table of a snapshot to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["name", "ip", "send_mbps", "recv_mbps",
                        "total_sent_mb", "total_recv_mb", "errors_in", "errors_out"],
        )
        writer.writeheader()
        for iface in snapshot.interfaces:
            writer.writerow(iface.to_dict())
    return path


def run_demo() -> int:
    """Take two snapshots so the rate calculation has a delta to report."""
    print(BANNER)
    reset_counters()
    print("Sampling interfaces (first pass establishes a baseline)...\n")
    take_snapshot()

    import time

    time.sleep(1.0)
    snapshot = take_snapshot()
    print(format_snapshot(snapshot))
    print("\nDemo completed successfully.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Host network monitor")
    parser.add_argument("--demo", action="store_true", help="take two snapshots and exit")
    parser.add_argument("--watch", action="store_true", help="refresh continuously")
    parser.add_argument("--interval", type=float, default=2.0, help="refresh interval seconds")
    parser.add_argument("--count", type=int, default=1, help="number of snapshots in watch mode")
    parser.add_argument("--csv", type=Path, default=None, help="write interface table to CSV")
    parser.add_argument("--json", type=Path, default=None, help="write full snapshot to JSON")
    parser.add_argument("--connections", type=int, default=50, help="max connections listed")
    parser.add_argument("--top", type=int, default=5, help="number of top talkers")
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    try:
        from monitor import require_psutil

        require_psutil()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(BANNER)
    reset_counters()

    cycles = args.count if args.watch else 1
    try:
        for index in range(max(1, cycles)):
            snapshot = take_snapshot(args.connections, args.top)
            print(format_snapshot(snapshot))
            print(f"\n--- snapshot {index + 1}/{cycles} ---")

            if args.csv:
                print("Wrote", write_csv(snapshot, args.csv))
            if args.json:
                args.json.parent.mkdir(parents=True, exist_ok=True)
                args.json.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
                print("Wrote", args.json)

            if args.watch and index < cycles - 1:
                import time

                time.sleep(max(0.1, args.interval))
    except KeyboardInterrupt:
        print("\nStopped.")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
