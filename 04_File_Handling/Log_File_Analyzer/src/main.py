"""Command line for Log_File_Analyzer.

    python src/main.py --demo
    python src/main.py                 # the level table and the span
    python src/main.py --levels        # per file, all five levels
    python src/main.py --malformed     # every line that is not an entry
    python src/main.py --search error
    python src/main.py --legacy        # the substring chain, side by side
    python src/main.py --report out.csv
    python src/main.py --json out.json
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyzer
from analyzer import (LEGACY_CHAIN, LEGACY_EXTENSIONS, LEGACY_LINE, LEVELS,
                      LOGS, LogError, analyze, legacy_classify, legacy_counts,
                      legacy_lines, legacy_unknowns, report_text, search)


def _summary(analysis) -> None:
    summary = analysis.summary()
    print(f"  folder       {analysis.root}")
    print(f"  files        {summary['files']} ({summary['blobs']} bytes)")
    print(f"  lines        {summary['nonblank']} non-blank")
    print(f"  entries      {summary['entries']}")
    print(f"  continued    {summary['continuations']} lines belong to an entry")
    print(f"  malformed    {summary['malformed']} lines are not entries")
    print("  levels       " + "  ".join(f"{level} {summary[level]}"
                                       for level in LEVELS))
    try:
        first, last, seconds = analysis.span()
        print(f"  span         {first} to {last} ({seconds} s)")
    except LogError:
        print("  span         no entries, so no span")


def _levels(analysis) -> None:
    width = max(16, *(len(report.name) for report in analysis.files))
    header = f"  {'file':<{width}} {'entries':>7} " + \
        " ".join(f"{level:>8}" for level in LEVELS)
    print(header)
    for report in analysis.files:
        counts = report.counts()
        row = f"  {report.name:<{width}} {len(report.entries):>7} " + \
            " ".join(f"{counts[level]:>8}" for level in LEVELS)
        print(row)
    counts = analysis.counts()
    print(f"  {'TOTAL':<{width}} {len(analysis):>7} " +
          " ".join(f"{counts[level]:>8}" for level in LEVELS))
    print("  every level is printed for every file, so a zero is a measurement")


def _malformed(analysis) -> None:
    bad = analysis.bad
    if not bad:
        print("  every non-blank line parsed as an entry or a continuation")
        return
    for line in bad:
        print(f"  {line.file}:{line.line}  {line.text}")
        print(f"      {line.reason}")
    print(f"\n  {len(bad)} malformed line(s) in "
          f"{len({line.file for line in bad})} file(s)")


def _entries(analysis, word: str) -> None:
    hits = search(analysis, word)
    noun = "entry" if len(hits) == 1 else "entries"
    print(f"  {len(hits)} {noun} whose message contains {word!r} as a whole "
          f"word")
    for entry in hits:
        print(f"    {entry.file}:{entry.line}  {entry.level:<8} "
              f"{entry.message}")
    if not hits:
        print("    nothing matched, and a substring inside a longer word "
              "would not have matched either")


def _legacy(analysis) -> int:
    counts = legacy_counts(legacy_lines(analysis))
    print("  the legacy chain, line by line:")
    for level in ("INFO", "WARNING", "ERROR", "CRITICAL", "UNKNOWN"):
        print(f"    {level:<9} {counts.get(level, 0)}")
    print(f"    {'DEBUG':<9} (no branch exists, so the level cannot be "
          f"reported)")

    print("\n  lines it cannot name, and what they really are:")
    real, others = legacy_unknowns(analysis)
    for name, number, text in others:
        print(f"    {name}:{number}  {text[:58]}")
        print(f"      not an entry")
    for name, number, text in real:
        print(f"    {name}:{number}  {text[:58]}")
        print(f"      a real DEBUG entry the chain has no branch for")

    print(f"\n  this module: {len(analysis)} entries with " +
          " ".join(f"{level} {analysis.counts()[level]}" for level in LEVELS))
    print(f"  the chain counted {sum(counts.values())} lines as "
          f"{sum(counts.values())} entries")
    print(f"  {LEGACY_LINE!r}")
    print(f"  {LEGACY_EXTENSIONS}")
    print(f"  the chain is {LEGACY_CHAIN}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="log-analyzer",
        description="Count log levels by field, keep every malformed line, "
                    "and search messages as words.")
    parser.add_argument("--logs", default=None,
                        help="the folder to read (default: the bundled logs)")
    parser.add_argument("--levels", action="store_true",
                        help="the per-file table, every level present")
    parser.add_argument("--malformed", action="store_true",
                        help="every line that is not an entry, with its reason")
    parser.add_argument("--search", default=None, metavar="WORD",
                        help="entries whose message contains WORD as a word")
    parser.add_argument("--legacy", action="store_true",
                        help="what the substring chain reports")
    parser.add_argument("--report", default=None, metavar="PATH",
                        help="write the per-file table as CSV to PATH")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the whole analysis as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if not args.quiet:
            return analyzer.run_demo()
        with contextlib.redirect_stdout(io.StringIO()):
            return analyzer.run_demo()

    folder = Path(args.logs) if args.logs else LOGS

    try:
        analysis = analyze(folder)

        if args.legacy:
            if not args.quiet:
                return _legacy(analysis)
            with contextlib.redirect_stdout(io.StringIO()):
                return _legacy(analysis)

        if args.search is not None:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    _entries(analysis, args.search)
            else:
                _entries(analysis, args.search)
            return 0

        if args.malformed:
            if not args.quiet:
                _malformed(analysis)
            return 0

        if args.report:
            target = Path(args.report)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(report_text(analysis), encoding="utf-8")
            if not args.quiet:
                print(f"  wrote {len(analysis.files) + 1} row(s) to {target}")
            return 0

        if args.json:
            target = Path(args.json)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(analysis.to_dict(), indent=2) + "\n",
                              encoding="utf-8")
            if not args.quiet:
                print(f"  wrote {len(analysis)} entries to {target}")
            return 0

        if args.quiet:
            return 0

        _summary(analysis)
        print()
        _levels(analysis)
        return 0
    except LogError as exc:
        print(f"  {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
