"""Command line entry point for the Hash Cracker.

Usage
-----
    python src/main.py --demo                              # crack bundled samples offline
    python src/main.py --hash <hex> --algo sha256          # dictionary attack
    python src/main.py --hash <hex> --mode bruteforce --charset digits --max-len 4
    python src/main.py --hash <hex> --wordlist mine.txt    # own wordlist

Ethics: only crack hashes you own or are explicitly authorized to test.
Everything runs locally - no network access.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from cracker import (
    CHARSETS,
    SUPPORTED_ALGOS,
    CrackerError,
    crack,
    hash_text,
    render_result,
    run_demo,
    verify,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("hash_cracker")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline hash cracker (authorized hashes only)"
    )
    parser.add_argument("--hash", default=None, help="hex digest to crack")
    parser.add_argument("--algo", default="sha256",
                        choices=sorted(SUPPORTED_ALGOS), help="hash algorithm")
    parser.add_argument("--mode", default="dictionary",
                        choices=["dictionary", "bruteforce", "hybrid"],
                        help="attack mode")
    parser.add_argument("--wordlist", default=None, help="path to your wordlist")
    parser.add_argument("--no-mutations", action="store_true",
                        help="disable password mutations in dictionary mode")
    parser.add_argument("--charset", default=None,
                        choices=sorted(CHARSETS), help="brute-force character set")
    parser.add_argument("--max-len", type=int, default=4,
                        help="brute-force maximum length (default 4, hard cap 8)")
    parser.add_argument("--min-len", type=int, default=1,
                        help="brute-force minimum length")
    parser.add_argument("--budget", type=float, default=10.0,
                        help="time budget in seconds for each attack stage")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--hash-text", default=None,
                        help="hash a string and print the digest, then exit")
    parser.add_argument("--verify", nargs=2, metavar=("TEXT", "DIGEST"),
                        default=None, help="check a candidate against a digest")
    parser.add_argument("--demo", action="store_true", help="run the offline demo")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    try:
        if args.hash_text is not None:
            digest = hash_text(args.hash_text, args.algo)
            print(digest)
            return 0

        if args.verify is not None:
            text, digest = args.verify
            ok = verify(text, digest, args.algo)
            print("MATCH" if ok else "NO MATCH")
            return 0 if ok else 1

        if not args.hash:
            parser.error("provide --hash, --hash-text, --verify, or --demo")

        if args.max_len > 8:
            print("Error: --max-len capped at 8 to keep searches bounded",
                  file=sys.stderr)
            return 2

        result = crack(
            args.hash,
            args.algo,
            wordlist=args.wordlist,
            use_mutations=not args.no_mutations,
            charset=CHARSETS[args.charset] if args.charset else None,
            max_length=args.max_len,
            min_length=args.min_len,
            time_budget_s=args.budget,
            mode=args.mode,
        )
    except CrackerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        payload = result.to_dict()
        payload["digest"] = args.hash
        print(json.dumps(payload, indent=2))
    else:
        print(render_result(result, args.hash))

    return 0 if result.found else 1


if __name__ == "__main__":
    raise SystemExit(main())
