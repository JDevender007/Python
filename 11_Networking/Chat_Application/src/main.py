"""Command line front end for the chat framing lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chat import (                                          # noqa: E402
    LOG_FILE,
    READ_LIMIT,
    ChatError,
    FrameDecoder,
    audit,
    converse,
    encode_frame,
    legacy_deliver,
    measure,
    parse_log,
    problems,
    read_log,
    run_demo,
    split_reads,
    wire_of,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chat-lab",
        description="Frame a message by its byte count, and hold half a frame.")
    parser.add_argument("--file", default=None, metavar="PATH",
                        help="a chat log (default: the bundled one)")
    parser.add_argument("--chunk", default=READ_LIMIT, type=int, metavar="BYTES",
                        help=f"how many bytes one read returns "
                             f"(default: {READ_LIMIT})")
    parser.add_argument("--legacy", action="store_true",
                        help="deliver with the old newline splitter as well")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the messages and the measurements to PATH")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        messages = read_log(args.file)
        if args.chunk <= 0 or args.chunk > 65536:
            raise ChatError(f"a read limit is 1..65536, got {args.chunk}")
        server, wire = converse(messages, args.chunk)
        legacy = legacy_deliver(split_reads(wire, args.chunk))
    except ChatError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {len(messages)} messages, {len(wire)} bytes, "
              f"{server.reads} reads of {args.chunk} bytes")
        print(f"  {server.partial_reads} read(s) ended mid-frame")
        print("  delivered:")
        for text in server.delivered:
            print(f"    {ascii(text)}")
        if args.legacy:
            print(f"  the legacy reader delivers {len(legacy)} line(s):")
            for line in legacy:
                print(f"    {ascii(line)}")

    checks = []
    measured: dict = {}
    if args.audit:
        measured = measure(messages, args.chunk)
        checks = audit(measured, messages, read_limit=args.chunk)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)
    else:
        failed = []

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "file": str(args.file) if args.file else LOG_FILE.name,
            "chunk": args.chunk,
            "messages": [
                {
                    "sender": message.sender,
                    "text": message.text,
                    "characters": message.characters,
                    "bytes": message.size,
                    "frame": encode_frame(message.text).decode("utf-8"),
                    "legacy_lines": len(legacy_deliver(
                        [encode_frame(message.text)])),
                }
                for message in messages
            ],
            "reads": server.reads,
            "partial_reads": server.partial_reads,
            "delivered": list(server.delivered),
            "legacy": list(legacy),
            "measurements": measured,
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the conversation to {destination}")

    if failed:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
