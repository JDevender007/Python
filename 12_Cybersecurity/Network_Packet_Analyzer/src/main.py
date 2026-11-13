"""Command line entry point for the Network Packet Analyzer.

Usage
-----
    python src/main.py --demo                        # synthetic offline capture
    python src/main.py --pcap capture.pcap           # analyse a pcap file
    python src/main.py --pcap capture.pcap --proto TCP --host 10.0.0.5
    python src/main.py --pcap capture.pcap --port 443 --top 10 --json out.json

Live capture (--live) needs Npcap/WinPcap and authorization on the network;
only capture traffic you are allowed to see.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from packet_analyzer import (
    apply_filters,
    analyze,
    load_pcap,
    records_from_packets,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("packet")

BANNER = """
========================================
 NETWORK PACKET ANALYZER
   offline analysis - pcap or demo
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline packet capture analyser")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="run the offline demo")
    source.add_argument("--pcap", type=Path, default=None, help="pcap/pcapng file to analyse")
    source.add_argument("--live", default=None, metavar="IFACE",
                        help="capture live traffic (requires Npcap + authorization)")
    parser.add_argument("--host", default=None, help="filter by IP (src or dst)")
    parser.add_argument("--proto", default=None,
                        help="filter by protocol: TCP, UDP, ICMP, DNS")
    parser.add_argument("--port", type=int, default=None, help="filter by port (src or dst)")
    parser.add_argument("--top", type=int, default=5, help="talkers/ports to show")
    parser.add_argument("--list", type=int, default=0, metavar="N",
                        help="list the first N packets")
    parser.add_argument("--json", type=Path, default=None, help="write JSON report to file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if args.live is not None:
        # Live capture needs Npcap on Windows and usually admin rights.
        try:
            from scapy.all import sniff  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment dependent
            print(f"Live capture unavailable: {exc}", file=sys.stderr)
            return 2
        print(
            "Live capture mode:\n"
            "  - requires Npcap/WinPcap and usually elevated privileges\n"
            "  - only capture networks you own or are authorized to monitor\n"
            "Use --demo or --pcap for fully offline analysis.\n"
            "Refusing to sniff by default; wire this into your own harness.",
            file=sys.stderr,
        )
        return 2

    assert args.pcap is not None
    print(BANNER)
    try:
        records = load_pcap(args.pcap)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    records = apply_filters(records, host=args.host, proto=args.proto, port=args.port)
    if not records:
        print("No packets match the given filters.")
        return 0

    report = analyze(records, top=max(1, args.top))
    print(render_report(report, show_packets=max(0, args.list)))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
