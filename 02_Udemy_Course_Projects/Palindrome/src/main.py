"""Command line interface for the Palindrome project.

    python src/main.py --demo
    python src/main.py                        # classify the bundled phrases
    python src/main.py --check "Taco cat"
    python src/main.py --complete race
    python src/main.py --longest forgeeksskeegfor
    python src/main.py --file my_phrases.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from palindrome import (
    PHRASES_FILE,
    PalindromeError,
    check,
    complete,
    is_palindrome,
    load_phrases,
    longest_palindromic_substring,
    mirror,
    normalise,
    run_demo,
    split_phrases,
    stats,
)

BANNER = """
====================================
 PALINDROME
   normalise, then complete
====================================
"""


def _row(phrase: str) -> str:
    verdict = check(phrase)
    mark = "yes" if verdict["palindrome"] else "no "
    return (f"  {mark}  {verdict['length']:>3}  {phrase}")


def _render(phrases: list[str]) -> str:
    if not phrases:
        return "  (no phrases)"
    return "\n".join(_row(phrase) for phrase in phrases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Palindrome checks, longest runs and minimal completion.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=PHRASES_FILE,
                        help="phrase file (default: data/phrases.txt)")
    parser.add_argument("--check", metavar="TEXT",
                        help="classify a single phrase")
    parser.add_argument("--complete", metavar="TEXT",
                        help="shortest palindrome that starts with TEXT")
    parser.add_argument("--mirror", metavar="TEXT",
                        help="the trivial TEXT + reverse(TEXT)")
    parser.add_argument("--longest", metavar="TEXT",
                        help="longest mirrored run inside TEXT")
    parser.add_argument("--stats", action="store_true",
                        help="counts and extremes for the phrase file")
    parser.add_argument("--json", type=Path, metavar="PATH",
                        help="write the result as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="write no standard output")
    args = parser.parse_args(argv)

    if args.demo:
        if args.quiet:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo()
        else:
            run_demo()
        return 0

    try:
        payload: dict = {}
        if args.check is not None:
            payload = {"mode": "check", "result": check(args.check)}
        elif args.complete is not None:
            result = complete(args.complete)
            payload = {"mode": "complete", "input": args.complete,
                       "completed": result, "added": len(result) -
                       len(normalise(args.complete)),
                       "palindrome": is_palindrome(result)}
        elif args.mirror is not None:
            result = mirror(args.mirror)
            payload = {"mode": "mirror", "input": args.mirror,
                       "mirror": result, "length": len(result)}
        elif args.longest is not None:
            result = longest_palindromic_substring(args.longest)
            payload = {"mode": "longest", "input": args.longest,
                       "longest": result, "length": len(result),
                       "whole": result == normalise(args.longest)}
        else:
            phrases = load_phrases(args.file)
            yes, no = split_phrases(phrases)
            payload = {"mode": "stats" if args.stats else "list",
                       "file": args.file.name,
                       "phrases": [check(phrase) for phrase in phrases],
                       "palindromes": len(yes), "others": len(no),
                       "stats": stats(phrases)}

        if not args.quiet and payload["mode"] == "check":
            result = payload["result"]
            print(BANNER)
            print(f"  input      {result['raw']}")
            print(f"  cleaned    {result['cleaned']}")
            print(f"  reversed   {result['reversed']}")
            print(f"  verdict    {'palindrome' if result['palindrome'] else 'not a palindrome'}")
        elif not args.quiet and payload["mode"] == "complete":
            print(BANNER)
            print(f"  input      {payload['input']}")
            print(f"  completed  {payload['completed']}")
            print(f"  added      {payload['added']} character(s)")
        elif not args.quiet and payload["mode"] == "mirror":
            print(BANNER)
            print(f"  input      {payload['input']}")
            print(f"  mirrored   {payload['mirror']}")
            print(f"  length     {payload['length']} (double, minus nothing)")
        elif not args.quiet and payload["mode"] == "longest":
            print(BANNER)
            print(f"  input      {payload['input']}")
            print(f"  longest    {payload['longest']}")
            print(f"  length     {payload['length']}"
                  f"{' (the whole phrase)' if payload['whole'] else ''}")
        elif not args.quiet:
            print(BANNER)
            print(_render([item["raw"] for item in payload["phrases"]]))
            print(f"\n  {payload['palindromes']} palindrome(s), "
                  f"{payload['others']} other(s)")
            if payload["mode"] == "stats":
                summary = payload["stats"]
                print(f"  longest phrase  {summary['longest']!r} "
                      f"({summary['longest_length']} chars)")
                print(f"  shortest        {summary['shortest_length']} chars")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except PalindromeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
