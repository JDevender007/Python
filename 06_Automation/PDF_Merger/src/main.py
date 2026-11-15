"""Command line front end for the PDF lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdfdocument import (                                   # noqa: E402
    PdfError,
    audit,
    build_lab,
    check,
    check_files,
    count_pages,
    count_pages_naive,
    merge,
    problems,
    read_bundle,
    render,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-lab",
        description="Validate PDFs before merging them, say why a file cannot "
                    "be read, and count pages by reading objects rather than "
                    "by matching a prefix.")
    parser.add_argument("--file", nargs="*", default=None, metavar="PATH",
                        help="the PDFs to merge, in order")
    parser.add_argument("--output", default="merged.pdf", metavar="PATH",
                        help="where to write the merge (default: merged.pdf)")
    parser.add_argument("--bundle", default=None, metavar="PATH",
                        help="a pages.txt bundle to use as the inputs "
                             "(default: the bundled one)")
    parser.add_argument("--write", default=None, metavar="DIR",
                        help="write the bundle out as real PDFs in DIR, then "
                             "stop")
    parser.add_argument("--pages", action="store_true",
                        help="print the merged page map")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the report to PATH as JSON")
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
        needed = bool(args.bundle) or not args.file or bool(args.write)
        bundle = read_bundle(args.bundle) if needed else {}
    except PdfError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.write:
        target = Path(args.write)
        target.mkdir(parents=True, exist_ok=True)
        for name, document in bundle.items():
            written = target / f"{name}.pdf"
            written.write_bytes(render(document))
            if not args.quiet:
                print(f"  wrote {document.size()} to {written}")
        return 0

    if args.file:
        report = check_files(args.file, args.output)
        sources = tuple((name, None) for name in args.file)
    else:
        written = {name: render(document) for name, document in bundle.items()}
        sources = tuple(written.items())
        report = check(sources, args.output)

    merged = merge(report.read()) if report.ok() else None
    output_bytes = render(merged) if merged is not None else b""

    if merged is not None:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(output_bytes)

    if not args.quiet:
        print(f"  {report.summary()}, output {report.output}")
        for line in report.lines():
            print(f"    {line}")

        if merged is None:
            print("  nothing was merged and nothing was written")
        else:
            print(f"  merged: {merged.size()} -> {len(output_bytes)} bytes")
            if args.pages:
                for line in merged.lines():
                    print(f"    {line}")
            print(f"  wrote {args.output}: starts {output_bytes[:8]!r}, holds "
                  f"{count_pages(output_bytes)} page object(s) where the "
                  f"substring count says {count_pages_naive(output_bytes)}")

    failed_checks = []
    if args.audit:
        parts = tuple(bundle[name] for name in bundle) if not args.file else \
            tuple(report.read())
        lab = build_lab(parts, [name for name, _ in sources])
        print()
        checks = audit(lab)
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "output": report.output,
            "ok": report.ok(),
            "inputs": [{"name": reading.name,
                        "pages": None if reading.document is None
                        else len(reading.document),
                        "reason": reading.reason}
                       for reading in report.readings],
            "problems": [{"name": problem.name, "reason": problem.reason}
                         for problem in report.problems],
            "merged_pages": [] if merged is None else list(merged.titles()),
            "merged_bytes": len(output_bytes),
        }
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the report to {target}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    return 0 if report.ok() else 1


if __name__ == "__main__":
    raise SystemExit(main())
