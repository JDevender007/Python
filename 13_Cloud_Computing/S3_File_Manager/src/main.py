"""Command line entry point for the S3 File Manager.

Usage
-----
    python src/main.py --demo                          # offline Stubber demo
    python src/main.py --list --bucket my-bucket
    python src/main.py --put ./file.txt --key file.txt --bucket my-bucket
    python src/main.py --get --key file.txt --out copy.txt --bucket my-bucket
    python src/main.py --delete --key file.txt --bucket my-bucket
    python src/main.py --url --key file.txt --bucket my-bucket

Real operations use the standard AWS credential chain (env vars, ~/.aws,
instance role). The demo needs none of that - it runs against a stub client.
Only manage buckets you own or are authorized to touch.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from s3_manager import S3Error, S3Manager, live_client, run_demo

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("s3")

BANNER = """
========================================
 S3 FILE MANAGER
   authorized buckets only
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="S3 file management (authorized buckets only)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true", help="run the offline demo")
    action.add_argument("--list", action="store_true", help="list objects")
    action.add_argument("--put", type=Path, metavar="FILE", help="upload a local file")
    action.add_argument("--get", action="store_true", help="download an object")
    action.add_argument("--delete", action="store_true", help="delete an object")
    action.add_argument("--url", action="store_true", help="presigned GET URL")

    parser.add_argument("--bucket", default=os.environ.get("S3_BUCKET"),
                        help="bucket name (or env S3_BUCKET)")
    parser.add_argument("--key", default=None, help="object key")
    parser.add_argument("--out", type=Path, default=None, help="output path for --get")
    parser.add_argument("--prefix", default="", help="key prefix for --list")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"),
                        help="AWS region")
    parser.add_argument("--endpoint-url", default=os.environ.get("AWS_ENDPOINT_URL"),
                        help="custom endpoint (MinIO, LocalStack, R2)")
    parser.add_argument("--expires", type=int, default=3600,
                        help="presign lifetime seconds for --url")
    parser.add_argument("--json", action="store_true", help="JSON output where applicable")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if not args.bucket:
        print("Error: --bucket is required (or set S3_BUCKET)", file=sys.stderr)
        return 2
    if (args.get or args.delete or args.url) and not args.key:
        print("Error: --key is required for this action", file=sys.stderr)
        return 2
    if args.put and not args.key:
        print("Error: --key is required for --put", file=sys.stderr)
        return 2

    print(BANNER)
    manager = S3Manager(
        args.bucket,
        client=live_client(args.region, args.endpoint_url),
        region=args.region,
        endpoint_url=args.endpoint_url,
    )

    try:
        if args.list:
            objects = manager.list_objects(args.prefix)
            if args.json:
                import json

                print(json.dumps([o.to_dict() for o in objects], indent=2))
            elif not objects:
                print("(no objects)")
            else:
                total = 0
                for obj in objects:
                    total += obj.size
                    print(f"  {obj.size:>10}  {obj.key}")
                print(f"  {len(objects)} object(s), {total} bytes")
        elif args.put:
            if not args.put.is_file():
                print(f"Error: file not found: {args.put}", file=sys.stderr)
                return 2
            etag = manager.upload_file(args.put, args.key or args.put.name)
            print(f"Uploaded {args.put} -> s3://{args.bucket}/{args.key or args.put.name}")
            print(f"ETag: {etag}")
        elif args.get:
            target = args.out or Path(args.key or "download").name
            manager.download_file(args.key or "", target)
            print(f"Downloaded s3://{args.bucket}/{args.key} -> {target} "
                  f"({target.stat().st_size} bytes)")
        elif args.delete:
            manager.delete(args.key or "")
            print(f"Deleted s3://{args.bucket}/{args.key}")
        elif args.url:
            url = manager.presigned_url(args.key or "", expires=args.expires)
            print(url)
    except S3Error as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
