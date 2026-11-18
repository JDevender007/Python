"""Command line front end for the S3 bucket lab.

Usage:
    python src/main.py --demo
    python src/main.py --demo --quiet
    python src/main.py --file data/bucket.json --json out.json
    python src/main.py --prefix logs/ --delimiter /
    python src/main.py --file data/bucket.json --audit
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

from s3_manager import (                                    # noqa: E402
    DEFAULT_EXPIRES,
    DEFAULT_PAGE_SIZE,
    BucketError,
    audit,
    measure,
    presign,
    render_listing,
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
        prog="s3-bucket-lab",
        description="Page and verify a bundled S3 bucket manifest, fully offline.",
    )
    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    parser.add_argument("--quiet", action="store_true", help="with --demo, print nothing")
    parser.add_argument(
        "--file",
        default=None,
        metavar="BUCKET_JSON",
        help="bucket manifest to read; defaults to data/bucket.json",
    )
    parser.add_argument(
        "--prefix", default="logs/", help="key prefix to query (default: logs/)"
    )
    parser.add_argument(
        "--delimiter",
        default="/",
        help="delimiter that turns a prefix into folders; empty means none",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"objects per page (default: {DEFAULT_PAGE_SIZE})",
    )
    parser.add_argument(
        "--expires",
        type=int,
        default=DEFAULT_EXPIRES,
        help=f"presigned URL lifetime in seconds (default: {DEFAULT_EXPIRES})",
    )
    parser.add_argument("--json", default=None, metavar="PATH", help="write a JSON report")
    parser.add_argument("--audit", action="store_true", help="re-run the checks; exit 1 on failure")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo, args.file)
        except BucketError as exc:
            if not args.quiet:
                print(f"error: {exc}", file=sys.stderr)
            return 0

    delimiter = args.delimiter or None
    try:
        measured = measure(args.file, args.prefix, delimiter, args.page_size)
        url = presign(measured["manifest"], "reports/q3 final.txt", args.expires)
    except BucketError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.audit:
        results = audit(measured)
        for name, okay in results:
            print(f"{'PASS' if okay else 'FAIL'}  {name}")
        failed = [name for name, okay in results if not okay]
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
        print(render_listing(measured["listing"], args.prefix, measured["manifest"].bucket))
        print()
        print(f"{'key':<26} {'bytes':>6}  {'kind':<10} etag")
        for record in measured["manifest"].objects:
            print(
                f"{record.key:<26} {record.size:>6}  {record.kind:<10} {record.etag}"
            )
        print()
        print(f"legacy first page: {', '.join(measured['query']['legacy'])}")
        print(f"presigned: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
