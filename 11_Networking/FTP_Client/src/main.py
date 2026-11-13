"""Command line entry point for the FTP Client.

Usage
-----
    python src/main.py --demo                       # offline in-memory demo
    python src/main.py --host 127.0.0.1 --user me --password pw --list
    python src/main.py --host ... --upload local.txt
    python src/main.py --host ... --download remote.txt

Only connect to FTP servers you own or are authorized to use.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ftp_client import DEFAULT_HOST, FTPClient, FTPError, run_demo

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("ftp")

BANNER = """
========================================
 FTP CLIENT
 authorized servers only
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FTP client (authorized servers only)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="FTP host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=21, help="FTP port")
    parser.add_argument("--user", default="anonymous", help="username")
    parser.add_argument("--password", default="anonymous@", help="password")
    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    parser.add_argument("--list", action="store_true", help="list remote directory")
    parser.add_argument("--path", default="", help="remote path for --list")
    parser.add_argument("--upload", type=Path, default=None, help="local file to upload")
    parser.add_argument("--download", default=None, help="remote file to download")
    parser.add_argument("--remote-name", default=None, help="remote name for --upload")
    parser.add_argument("--mkdir", default=None, help="create a remote directory")
    parser.add_argument("--delete", default=None, help="delete a remote file")
    parser.add_argument("--timeout", type=float, default=10.0, help="socket timeout seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        print(BANNER)
        return run_demo()

    actions = [args.list, args.upload, args.download, args.mkdir, args.delete]
    if not any(actions):
        parser.error("choose an action: --list, --upload, --download, --mkdir, --delete (or --demo)")

    client = FTPClient(host=args.host, port=args.port, timeout=args.timeout)
    try:
        banner = client.connect(args.user, args.password)
        print(BANNER)
        print("Server:", banner)

        if args.list:
            entries = client.list(args.path)
            if not entries:
                print("  (empty)")
            for entry in entries:
                print(" ", entry)

        if args.upload:
            sent = client.upload(args.upload, args.remote_name)
            print(f"Uploaded {args.upload} ({sent} bytes)")

        if args.download:
            path = client.download(args.download)
            print(f"Downloaded -> {path}")

        if args.mkdir:
            client.make_directory(args.mkdir)
            print(f"Created directory {args.mkdir}")

        if args.delete:
            client.delete(args.delete)
            print(f"Deleted {args.delete}")
    except FTPError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
