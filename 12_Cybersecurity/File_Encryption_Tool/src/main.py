"""Command line entry point for the File Encryption Tool.

Usage
-----
    python src/main.py --demo                                   # offline round-trip demo
    python src/main.py --encrypt notes.txt                      # -> notes.txt.enc
    python src/main.py --encrypt notes.txt --out out.enc
    python src/main.py --decrypt out.enc --out notes.txt
    python src/main.py --info out.enc                           # header metadata only
    echo -n "pw" > pw.txt  (password file, no trailing newline recommended)

Passwords: --pass-file is preferred; --password is visible in shell history;
otherwise the tool prompts with getpass.
"""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import sys
from pathlib import Path

from crypto_tool import (
    CryptoToolError,
    decrypt_file,
    encrypt_file,
    file_info,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("crypto_tool")

BANNER = """
========================================
 FILE ENCRYPTION TOOL
   AES-256-GCM + scrypt, local only
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Authenticated file encryption (AES-256-GCM + scrypt)"
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true", help="run the offline demo")
    action.add_argument("--encrypt", type=Path, metavar="FILE",
                        help="encrypt FILE (default output: FILE.enc)")
    action.add_argument("--decrypt", type=Path, metavar="FILE",
                        help="decrypt FILE (default output: strip .enc)")
    action.add_argument("--info", type=Path, metavar="FILE",
                        help="show container metadata (no password needed)")
    parser.add_argument("--out", type=Path, default=None, help="output path")
    password = parser.add_mutually_exclusive_group()
    password.add_argument("--password", default=None,
                          help="password (prefer --pass-file or the prompt)")
    password.add_argument("--pass-file", type=Path, default=None,
                          help="file whose contents are the password")
    parser.add_argument("--json", action="store_true",
                        help="JSON output for --info")
    return parser


def resolve_password(args: argparse.Namespace, prompt: str) -> str | None:
    """Get the password from --pass-file, --password, or an interactive prompt."""
    if args.pass_file is not None:
        if not args.pass_file.is_file():
            print(f"Error: password file not found: {args.pass_file}", file=sys.stderr)
            return None
        # strip a single trailing newline so echo-generated files work
        text = args.pass_file.read_text(encoding="utf-8")
        return text.rstrip("\r\n")
    if args.password is not None:
        return args.password
    return getpass.getpass(prompt)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if args.info is not None:
        try:
            info = file_info(args.info)
        except CryptoToolError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(info.to_dict(), indent=2))
        else:
            print(f"File     : {args.info}")
            print(f"Version  : {info.version}")
            print(f"Salt     : {info.salt_hex}")
            print(f"Nonce    : {info.nonce_hex}")
            print(f"Size     : {info.total_size} bytes "
                  f"({info.payload_size} ciphertext + 37-byte header)")
        return 0

    print(BANNER)
    assert args.encrypt is not None or args.decrypt is not None
    is_encrypt = args.encrypt is not None
    source = args.encrypt if is_encrypt else args.decrypt

    password = resolve_password(args, f"Password for {source.name}: ")
    if password is None:
        return 2
    if not password:
        print("Error: password must not be empty", file=sys.stderr)
        return 2

    if args.out is not None:
        target = args.out
    elif is_encrypt:
        target = source.with_name(source.name + ".enc")
    else:
        name = source.name[:-4] if source.name.endswith(".enc") else source.name + ".dec"
        target = source.with_name(name)

    try:
        if is_encrypt:
            encrypt_file(source, target, password)
        else:
            decrypt_file(source, target, password)
    except CryptoToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1 if "wrong password or tampered" in str(exc) else 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    verb = "Encrypted" if is_encrypt else "Decrypted"
    print(f"{verb} {source} -> {target} ({target.stat().st_size} bytes)")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
