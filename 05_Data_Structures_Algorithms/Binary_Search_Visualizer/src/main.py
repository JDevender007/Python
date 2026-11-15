"""Command line front end for the search lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from search import (                                          # noqa: E402
    PRECONDITION,
    SearchError,
    audit,
    audit_pairs,
    binary_search,
    comparison_bound,
    count_of,
    first_index,
    last_index,
    legacy_note,
    legacy_sorted_index,
    legacy_wrong_value,
    linear_search,
    problems,
    read_numbers,
    run_demo,
)


def _row(result) -> str:
    where = "-" if not result.found else str(result.index)
    return (f"  {result.algorithm:<8}{len(result.values):>7}"
            f"{result.target:>8}{where:>7}{result.comparisons:>13}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="search-lab",
        description="Binary search a sequence that is already ascending, and "
                    "never sort a copy behind the caller's back.")
    parser.add_argument("--numbers", default=None,
                        help="a file with one integer per line "
                             "(default: the bundled numbers)")
    parser.add_argument("--target", type=int, default=None,
                        help="the value to search for (default: 23)")
    parser.add_argument("--linear", action="store_true",
                        help="search linearly as well, for comparison")
    parser.add_argument("--range", action="store_true",
                        help="the first index, the last index and the count")
    parser.add_argument("--legacy", action="store_true",
                        help="what sorting a copy does to the answer")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the results to PATH as JSON")
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
        numbers = read_numbers(args.numbers) if args.numbers else read_numbers()
    except SearchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    target = 23 if args.target is None else args.target

    try:
        binary = binary_search(numbers, target)
    except SearchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    linear = linear_search(numbers, target) if args.linear else None

    if args.quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            _row(binary)
        return 0

    print(f"  {len(numbers)} numbers: {' '.join(str(n) for n in numbers)}")
    print(f"  {'search':<8}{'items':>7}{'target':>8}{'index':>7}"
          f"{'comparisons':>13}")
    print(_row(binary))
    if linear is not None:
        print(_row(linear))
    print(f"  a hit on {len(numbers)} may take at most "
          f"{comparison_bound(len(numbers), True)} comparisons, a miss at most "
          f"{comparison_bound(len(numbers), False)}")

    if args.range:
        first = first_index(numbers, target)
        last = last_index(numbers, target)
        print(f"\n  target {target}: first {first}, last {last}, "
              f"count {count_of(numbers, target)}")

    if args.legacy:
        unsorted = [30, 10, 20]
        index = legacy_sorted_index(unsorted, 10)
        sort_line, _return_line = legacy_note()
        print(f"\n  the legacy function on {unsorted}, target 10:")
        print(f"    {sort_line}")
        print(f"    it returns index {index} and index {index} of the array "
              f"you passed is {legacy_wrong_value(unsorted, 10)}")
        print(f"    this module refuses that input: {PRECONDITION}")

    if args.audit:
        print()
        results = [binary] + ([linear] if linear is not None else [])
        checks = audit(results)
        if linear is not None:
            checks += audit_pairs([(binary_search(numbers, n),
                                    linear_search(numbers, n))
                                   for n in numbers])
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        if problems(results):
            print(f"  {len(problems(results))} check(s) failed", file=sys.stderr)
            return 1

    if args.json:
        target_path = Path(args.json)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"binary": binary.to_dict(),
                   "linear": None if linear is None else linear.to_dict()}
        target_path.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        print(f"  wrote {2 if linear else 1} result(s) to {target_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
