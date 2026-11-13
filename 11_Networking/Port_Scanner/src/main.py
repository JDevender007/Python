"""Command line entry point for the Port Scanner.

Usage
-----
    python src/main.py --demo                       # scan localhost, canned result
    python src/main.py --host 127.0.0.1 --ports 1-1024
    python src/main.py --host 127.0.0.1 --ports 80,443 --json out.json

Only scan systems you own or have explicit permission to test.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from scanner import DEFAULT_HOST, parse_ports, scan, summarize

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("port_scanner")

BANNER = """
========================================
 PORT SCANNER
 localhost / authorized targets only
========================================
"""


def print_table(results) -> None:
    """Print a simple aligned table of results."""
    if not results:
        print("  (no ports scanned)")
        return
    header = f"  {'PORT':<8}{'STATE':<10}{'SERVICE':<16}{'LATENCY':<12}ERROR"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for r in results:
        state = "open" if r.open else "closed"
        latency = f"{r.latency_ms} ms" if r.open else "-"
        print(f"  {r.port:<8}{state:<10}{r.service:<16}{latency:<12}{r.error}")


def run_demo() -> int:
    """Offline-friendly demo: scans localhost with a tiny port set."""
    print(BANNER)
    print("Scanning localhost ports 7, 9, 13, 80, 443, 3306 (fast, no privileges needed)...\n")
    ports = [7, 9, 13, 80, 443, 3306]
    results = scan(DEFAULT_HOST, ports, timeout=0.3, workers=20)
    print_table(results)
    print("\nSummary:", summarize(results))
    print("\nDemo completed successfully.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TCP port scanner (authorized targets only)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="target host (default: 127.0.0.1)")
    parser.add_argument("--ports", default=None, help="ports: '80,443' or '1-1024' or mixed")
    parser.add_argument("--timeout", type=float, default=1.0, help="per-port timeout seconds")
    parser.add_argument("--workers", type=int, default=100, help="concurrent workers")
    parser.add_argument("--json", type=Path, default=None, help="write JSON results to this file")
    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if not args.ports:
        parser.error("--ports is required (e.g. --ports 1-1024) or use --demo")

    try:
        ports = parse_ports(args.ports)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(BANNER)
    LOG.info("Scanning %s (%d ports)", args.host, len(ports))
    results = scan(args.host, ports, timeout=args.timeout, workers=args.workers)
    print_table(results)
    summary = summarize(results)
    print("\nSummary:", summary)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"summary": summary,
                        "results": [r.to_dict() for r in results]}, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
