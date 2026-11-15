"""Command line front end for the sorting lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sorts import (                                            # noqa: E402
    ALGORITHMS,
    STABLE,
    VALUES,
    SortError,
    audit,
    inversions,
    items_from_keys,
    legacy_label,
    legacy_merge_swaps,
    legacy_merge_writes,
    problems,
    quick_sort,
    read_values,
    run_demo,
)


def _table(results) -> None:
    print(f"  {'algorithm':<12}{'comparisons':>12}{'writes':>8}{'swaps':>7}"
          f"{'stable':>8}{'frames':>8}")
    for result in results:
        print(f"  {result.algorithm:<12}{result.comparisons:>12}"
              f"{result.writes:>8}{result.swaps:>7}"
              f"{'yes' if result.is_stable() else 'no':>8}"
              f"{len(result.frames):>8}")
    print("  a swap is two writes, so the write column can never be smaller "
          "than twice the swap column")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sorting-lab",
        description="Sort the bundled values with six algorithms and report "
                    "comparisons, writes and swaps separately.")
    parser.add_argument("--values", default=None,
                        help="a file with one integer per line "
                             "(default: the bundled values)")
    parser.add_argument("--sort", default=None, choices=sorted(ALGORITHMS),
                        help="run one algorithm instead of all six")
    parser.add_argument("--compare", action="store_true",
                        help="the legacy counter against the honest one")
    parser.add_argument("--worst", action="store_true",
                        help="quick sort on an already-sorted input")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write every result to PATH as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing")
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
        items = read_values(args.values) if args.values else read_values()
    except SortError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not items:
        print("error: the values file holds no integers", file=sys.stderr)
        return 2

    results = [ALGORITHMS[args.sort](items)] if args.sort else \
        [ALGORITHMS[name](items) for name in ALGORITHMS]

    if args.quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            _table(results)
        return 0

    print(f"  {len(items)} items, {inversions([item.key for item in items])} "
          f"inversions")
    _table(results)

    if args.compare:
        print()
        merge = next(r for r in results if r.algorithm == "merge") \
            if not args.sort else ALGORITHMS["merge"](items)
        print(f"  the legacy label is {legacy_label()!r}: it printed "
              f"{legacy_merge_writes(items)} for merge sort, which swaps "
              f"{legacy_merge_swaps(items)} times and writes "
              f"{merge.writes} placements")

    if args.worst:
        print()
        quadratic = quick_sort(items_from_keys(sorted(item.key for item in items)))
        print(f"  quick sort on the already-sorted input: "
              f"{quadratic.comparisons} comparisons "
              f"(n(n-1)/2 = {len(items) * (len(items) - 1) // 2})")

    if args.audit:
        print()
        for name, okay in audit(results):
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(results)
        if failed:
            print(f"  {len(failed)} check(s) failed", file=sys.stderr)
            return 1

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"values": [item.key for item in items],
                   "results": [result.to_dict() for result in results],
                   "stable": list(STABLE)}
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        print(f"  wrote {len(results)} result(s) to {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
