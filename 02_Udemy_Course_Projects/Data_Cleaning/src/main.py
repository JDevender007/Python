"""Command line entry point for the data cleaner.

Usage
-----
    python src/main.py --demo                       # self-checking demo
    python src/main.py                              # clean the bundled CSV
    python src/main.py --scans                      # clean the bundled scans
    python src/main.py --text "  Hello,  WORLD! "    # clean one string
    python src/main.py --legacy                     # show the two legacy bugs
    python src/main.py --file messy.csv --json out.json --quiet

The legacy mode exists so the bugs are reproducible from the command line
rather than only described in the README.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import json
import sys
from pathlib import Path

from cleaning import (
    LEADING_ZERO_NOTE,
    MESSY_FILE,
    SCAN_FILE,
    CleanError,
    broken_clean,
    clean_table,
    clean_text,
    legacy_clean,
    load_lines,
    load_messy,
    normalise,
    run_demo,
    sniff,
    tokens,
)

BANNER = """
====================================
 DATA CLEANING
   symbols, whitespace, types, rows
====================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean messy text and CSV rows, and reproduce the legacy "
                    "loop's two bugs (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=None,
                        help=f"CSV to clean (default: {MESSY_FILE.name})")
    parser.add_argument("--scans", action="store_true",
                        help="clean the bundled scan lines instead of a CSV")
    parser.add_argument("--text", metavar="TEXT", default=None,
                        help="clean one string and show its tokens")
    parser.add_argument("--legacy", action="store_true",
                        help="run the original loop and the half-fixed one")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the result as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def render_cell(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


def render_table(rows: list[dict]) -> str:
    if not rows:
        return "  (no rows)"
    columns = list(rows[0])
    widths = {column: max(len(column),
                          max(len(render_cell(row[column])) for row in rows))
              for column in columns}
    lines = ["  " + "  ".join(f"{column:<{widths[column]}}"
                              for column in columns),
             "  " + "  ".join("-" * widths[column] for column in columns)]
    for row in rows:
        lines.append("  " + "  ".join(
            f"{render_cell(row[column]):<{widths[column]}}"
            for column in columns))
    return "\n".join(lines)


def render_report(report: dict) -> str:
    order = ("rows_in", "rows_out", "duplicate_rows", "cells",
             "cells_changed", "blanks_to_none", "to_int", "to_float",
             "to_bool", "to_date", "kept_text")
    width = max(len(name) for name in order)
    return "\n".join(f"  {name:<{width}}  {report[name]:>4}" for name in order)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except CleanError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        if args.legacy:
            sample = "These+notes#reveal9Newton"
            legacy = legacy_clean(sample)
            try:
                broken_clean(sample)
            except TypeError as exc:
                broken_error = str(exc)
            else:
                broken_error = ""
            payload = {"mode": "legacy", "input": sample,
                       "legacy_output": legacy,
                       "legacy_is_unchanged": legacy == sample,
                       "broken_error": broken_error}
        elif args.text is not None:
            payload = {"mode": "text", "input": args.text,
                       "cleaned": clean_text(args.text),
                       "normalised": normalise(args.text),
                       "tokens": tokens(args.text),
                       "sniffed": render_cell(sniff(args.text))}
        elif args.scans:
            lines = load_lines(args.file or SCAN_FILE)
            payload = {"mode": "scans", "count": len(lines),
                       "lines": [{"raw": line, "cleaned": clean_text(line)}
                                 for line in lines]}
        else:
            rows = load_messy(args.file or MESSY_FILE)
            cleaned, report = clean_table(rows)
            payload = {"mode": "table", "rows": cleaned, "report": report,
                       "leading_zero_note": LEADING_ZERO_NOTE}
    except CleanError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        if payload["mode"] == "legacy":
            print(f"  input          {payload['input']!r}")
            print(f"  legacy output  {payload['legacy_output']!r}")
            print(f"  unchanged?     {payload['legacy_is_unchanged']}  "
                  f"(the filter never ran)")
            if payload["broken_error"]:
                print(f"  half-fixed     TypeError: "
                      f"{payload['broken_error']}")
            else:
                print("  half-fixed     no error (no punctuation in input)")
        elif payload["mode"] == "text":
            print(f"  cleaned     {payload['cleaned']!r}")
            print(f"  normalised  {payload['normalised']!r}")
            print(f"  tokens      {payload['tokens']}")
            print(f"  sniffed     {payload['sniffed']} "
                  f"({type(sniff(args.text)).__name__})")
        elif payload["mode"] == "scans":
            for entry in payload["lines"]:
                print(f"  {entry['cleaned']}")
            print(f"\n  {payload['count']} line(s) cleaned")
        else:
            print(render_table(payload["rows"]))
            print()
            print(render_report(payload["report"]))
            print(f"\n  note: {payload['leading_zero_note']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, indent=2,
                       default=lambda value: value.isoformat()
                       if isinstance(value, datetime.date) else str(value)),
            encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
