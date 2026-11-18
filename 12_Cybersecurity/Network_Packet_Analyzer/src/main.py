"""Command line front end for the packet analyser lab.

Usage:
    python src/main.py --demo
    python src/main.py --demo --quiet
    python src/main.py --file data/capture.txt --json out.json
    python src/main.py --file data/capture.txt --audit
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from packet_analyzer import (                                # noqa: E402
    PacketError,
    audit,
    measure,
    render_packets,
    report,
    run_demo,
)


def _run_demo(quiet: bool, func, *args, **kwargs) -> int:
    """Run the offline demo; with --quiet no stream prints anything."""
    if not quiet:
        return func(*args, **kwargs)
    level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(level)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="packet-lab",
        description="Decode a bundled IPv4 capture offline and show the legacy numbers beside it.",
    )
    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    parser.add_argument("--quiet", action="store_true", help="with --demo, print nothing")
    parser.add_argument(
        "--file",
        default=None,
        metavar="CAPTURE_TXT",
        help="capture text file, one 'index | hex bytes' record per line",
    )
    parser.add_argument("--json", default=None, metavar="PATH", help="write a JSON report")
    parser.add_argument("--audit", action="store_true", help="re-run the checks; exit 1 on failure")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except PacketError as exc:
            if not args.quiet:
                print(f"error: {exc}", file=sys.stderr)
            return 0
    try:
        measured = measure(args.file)
    except PacketError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.audit:
        results = audit(measured)
        for name, ok in results:
            print(f"{'PASS' if ok else 'FAIL'}  {name}")
        failed = [name for name, ok in results if not ok]
        if failed:
            print(f"error: {len(failed)} check(s) failed", file=sys.stderr)
            return 1
        return 0

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report(measured), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if not args.quiet:
        print(render_packets(measured))
        print(
            f"{len(measured['packets'])} packets, valid checksums "
            f"{measured['valid_checksums']}, bad {measured['bad_checksums']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
