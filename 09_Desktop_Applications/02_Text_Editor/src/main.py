"""Command line front end for the document lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from documents import (                                     # noqa: E402
    NOTES_FILE,
    Document,
    DocumentError,
    audit,
    detect_newline,
    encode,
    measure,
    problems,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="document-lab",
        description="Edit a document with undo, and save it without ever "
                    "truncating the file it replaces.")
    parser.add_argument("--file", default=None, metavar="PATH",
                        help="a document to read (default: the bundled note)")
    parser.add_argument("--edit", default=None, metavar="TEXT",
                        help="type TEXT at the end of the document")
    parser.add_argument("--save", default=None, metavar="PATH",
                        help="save the document to PATH")
    parser.add_argument("--newline", default=None, choices=("lf", "crlf"),
                        help="override the file's newline policy when saving")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the document to PATH as JSON")
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
        source = Document.load(args.file or NOTES_FILE)
        if args.newline is not None:
            source = Document(source.text, "\r\n" if args.newline == "crlf"
                              else "\n", source.name)
        if args.edit is not None:
            source.insert(args.edit)
        written = source.save(args.save) if args.save else None
    except DocumentError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {source.line()}")
        for number, line in enumerate(source.lines(), start=1):
            print(f"  {number:>3}  {line}")
        if written is not None:
            print(f"  wrote {written} byte(s) to {args.save}")

    checks = []
    failed: list[str] = []
    measured: dict = {}
    if args.audit:
        measured, scratch = measure(source)
        checks = audit(measured, scratch)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "document": {
                "name": source.name,
                "text": source.text,
                "lines": list(source.lines()),
                "newline": source.newline,
                "chars": len(source),
                "revision": source.revision,
                "dirty": source.dirty(),
                "undo_depth": source.undo_depth(),
                "redo_depth": source.redo_depth(),
                "line_count": source.line_count(),
            },
            "bytes": {
                "lf": len(encode(source.text, "\n")),
                "crlf": len(encode(source.text, "\r\n")),
            },
            "written": written,
            "measurements": {key: value for key, value in measured.items()},
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the document to {destination}")

    if failed:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
