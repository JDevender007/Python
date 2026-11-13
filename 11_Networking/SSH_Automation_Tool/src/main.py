"""Command line entry point for the SSH Automation Tool.

Usage
-----
    python src/main.py --demo                          # fully offline demo
    python src/main.py --host 127.0.0.1 --user me --password pw --cmd "uname -a"
    python src/main.py --host ... --key ~/.ssh/id_ed25519 --script cmds.txt
    python src/main.py --host ... --upload local.txt --remote /tmp/x.txt

Only connect to machines you own or have explicit authorization to manage.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
from pathlib import Path

from ssh_tool import DEFAULT_HOST, SSHError, SSHSession, run_demo

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("ssh")

BANNER = """
========================================
 SSH AUTOMATION TOOL
   authorized hosts only
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SSH command & file automation (authorized hosts only)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="target host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=22, help="SSH port")
    parser.add_argument("--user", default=None, help="username (prompted if omitted)")
    parser.add_argument("--password", default=None, help="password (prefer --key or prompt)")
    parser.add_argument("--key", type=Path, default=None, help="path to a private key file")
    parser.add_argument("--timeout", type=float, default=10.0, help="connection timeout seconds")
    parser.add_argument("--cmd", action="append", default=[], help="command to run (repeatable)")
    parser.add_argument("--script", type=Path, default=None, help="file with one command per line")
    parser.add_argument("--upload", type=Path, default=None, help="local file to upload")
    parser.add_argument("--download", default=None, help="remote file to download")
    parser.add_argument("--remote", default=None, help="remote path for --upload / --download")
    parser.add_argument("--json", type=Path, default=None, help="write command results to JSON")
    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    return parser


def collect_commands(args: argparse.Namespace) -> list[str]:
    """Merge --cmd flags with the lines of --script (comments and blanks skipped)."""
    commands = list(args.cmd)
    if args.script:
        for line in args.script.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                commands.append(stripped)
    return commands


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        print(BANNER)
        return run_demo()

    commands = collect_commands(args)
    has_action = bool(commands or args.upload or args.download)
    if not has_action:
        parser.error("choose an action: --cmd, --script, --upload, --download (or --demo)")

    username = args.user or getpass.getuser()
    password = args.password
    if password is None and args.key is None:
        password = getpass.getpass(f"Password for {username}@{args.host}: ")

    session = SSHSession(
        host=args.host,
        port=args.port,
        username=username,
        password=password,
        key_path=args.key,
        timeout=args.timeout,
    )

    try:
        session.connect()
    except SSHError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(BANNER)
    exit_code = 0
    results = []
    try:
        for command in commands:
            result = session.run(command)
            results.append(result.to_dict())
            marker = "OK " if result.ok else f"[{result.exit_status}]"
            print(f"  {marker} $ {command}")
            if result.stdout:
                for line in result.stdout.rstrip("\n").splitlines():
                    print(f"       {line}")
            if result.stderr:
                for line in result.stderr.rstrip("\n").splitlines():
                    print(f"       ! {line}")
            if not result.ok:
                exit_code = result.exit_status or 1

        if args.upload:
            remote = args.remote or f"/tmp/{args.upload.name}"
            sent = session.upload(args.upload, remote)
            print(f"  uploaded {args.upload} -> {remote} ({sent} bytes)")

        if args.download:
            target = Path(args.remote) if args.remote else Path(args.download).name
            path = session.download(args.download, target)
            print(f"  downloaded {args.download} -> {path}")
    except SSHError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()

    if args.json:
        import json

        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"  wrote {args.json}")

    print("Done.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
