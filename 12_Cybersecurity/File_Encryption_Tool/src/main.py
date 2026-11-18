"""Command line front end for the file lab.

Usage
-----
    python src/main.py --demo
    python src/main.py --demo --quiet
    python src/main.py --file data/secret_note.txt --flip 0
    python src/main.py --audit
    python src/main.py --file data/secret_note.txt --json report.json
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crypto_tool import (                                   # noqa: E402
    DEMO_PASSWORD,
    HEADER_SIZE,
    NONCE,
    TAG_SIZE,
    DomainError,
    audit,
    derive_key,
    flip_byte,
    inspect,
    legacy_decrypt,
    legacy_encrypt,
    measure,
    problems,
    read_note,
    run_demo,
    seal,
    unseal,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file-lab",
        description="Seal a note so a flipped byte is refused, not decrypted.")
    parser.add_argument("--file", default=None, metavar="PATH",
                        help="an ASCII note (default: the bundled one)")
    parser.add_argument("--password", default=DEMO_PASSWORD, metavar="TEXT",
                        help="the key password (default: the demo password)")
    parser.add_argument("--flip", default=0, type=int, metavar="N",
                        help="flip byte N of both forms (default: 0)")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the measurements to PATH")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def _run_demo(quiet: bool) -> int:
    if not quiet:
        return run_demo()
    with contextlib.redirect_stdout(io.StringIO()):
        return run_demo()


def _plain(value):
    """Make a measurement JSON-safe without losing a byte."""
    if isinstance(value, bytes):
        return value.decode("ascii", "backslashreplace")
    return value


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        return _run_demo(args.quiet)

    try:
        note = read_note(args.file)
        if not args.password:
            raise DomainError("a password is text, and not empty")
        if not 0 <= args.flip < len(note):
            raise DomainError(f"a flip index is inside the {len(note)}-byte "
                              f"note, got {args.flip}")
    except DomainError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    key = derive_key(args.password)
    container = seal(note, key, NONCE)
    opened = unseal(container, key)
    checked = inspect(container)

    legacy = legacy_encrypt(note, args.password)
    legacy_tampered = legacy_decrypt(flip_byte(legacy, args.flip),
                                     args.password)
    try:
        unseal(flip_byte(container, HEADER_SIZE + args.flip), key)
    except DomainError as error:
        refusal = str(error)
    else:
        refusal = ""

    if not args.quiet:
        print(f"  note       {len(note)} bytes -> sealed {len(container)} bytes "
              f"({HEADER_SIZE} header + {TAG_SIZE} tag)")
        print(f"  round trip identical: {opened == note}")
        print(f"  nonce      {checked['nonce_hex']}")
        print(f"  flip {args.flip}: legacy gives "
              f"{legacy_tampered.decode('ascii', 'backslashreplace')!r}, "
              f"sealed refuses: {refusal or 'no'}")

    checks = []
    failed: list = []
    measured: dict = {}
    if args.audit:
        measured = measure(note, args.password)
        checks = audit(measured)
        if not args.quiet:
            print()
            for name, okay in checks:
                print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "note_bytes": len(note),
            "password": args.password,
            "flip": args.flip,
            "container": checked,
            "round_trip": opened == note,
            "legacy_tampered": legacy_tampered.decode("ascii",
                                                      "backslashreplace"),
            "sealed_refusal": refusal,
            "measurements": {name: _plain(value)
                             for name, value in measured.items()},
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="ascii")
        if not args.quiet:
            print(f"  wrote the report to {destination}")

    if failed:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
