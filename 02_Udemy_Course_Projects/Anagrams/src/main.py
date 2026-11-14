"""Command line entry point for the anagram finder.

Usage
-----
    python src/main.py --demo                        # self-checking demo
    python src/main.py                               # group the bundled words
    python src/main.py --check "listen" "silent"     # one pair
    python src/main.py --find listen                 # one word against the list
    python src/main.py --file words.txt              # your own word list
    python src/main.py --json out.json --quiet

Every comparison uses the same ``signature`` function, so a pair the CLI calls
an anagram is a pair the demo has already checked.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from anagram import (
    AnagramError,
    anagram_pairs,
    find_anagrams,
    group_anagrams,
    is_anagram,
    load_words,
    longest_group,
    run_demo,
    signature,
)

BANNER = """
====================================
 ANAGRAMS
   normalise, sign, group, search
====================================
"""

DEFAULT_FILE = (Path(__file__).resolve().parent.parent
                / "data" / "words.txt")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find anagram groups, pairs and matches in a word list "
                    "(offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=None,
                        help="word list (default: the bundled one)")
    parser.add_argument("--check", nargs=2, metavar=("FIRST", "SECOND"),
                        default=None, help="test one pair")
    parser.add_argument("--find", metavar="WORD", default=None,
                        help="anagrams of WORD inside the word list")
    parser.add_argument("--pairs", action="store_true",
                        help="list every anagram pair instead of the groups")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the result as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def render_groups(groups: dict[str, list[str]]) -> str:
    if not groups:
        return "  no anagram groups in this list"
    lines: list[str] = []
    for key, members in groups.items():
        lines.append(f"  {key:<{len(key)}}  {len(members)}  "
                     f"{', '.join(members)}")
    lines.append("")
    biggest = longest_group(groups)
    lines.append(f"  {len(groups)} group(s); largest has {len(biggest)} "
                 f"member(s): {', '.join(biggest)}")
    return "\n".join(lines)


def render_pairs(pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return "  no anagram pairs in this list"
    lines = [f"  {first_:<12}{second}" for first_, second in pairs]
    lines.append("")
    lines.append(f"  {len(pairs)} unordered pair(s)")
    return "\n".join(lines)


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
        except AnagramError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        if args.check is not None:
            first, second = args.check
            result = is_anagram(first, second)
            payload = {
                "mode": "check",
                "first": first,
                "second": second,
                "anagrams": result,
                "first_signature": signature(first),
                "second_signature": signature(second),
            }
        else:
            words = load_words(args.file or DEFAULT_FILE)
            if args.find is not None:
                hits = find_anagrams(args.find, words)
                payload = {"mode": "find", "word": args.find,
                           "matches": hits,
                           "signature": signature(args.find)}
            elif args.pairs:
                found = anagram_pairs(words)
                payload = {"mode": "pairs", "words": len(words),
                           "pairs": [list(pair) for pair in found]}
            else:
                groups = group_anagrams(words)
                payload = {
                    "mode": "groups",
                    "words": len(words),
                    "groups": groups,
                    "largest": longest_group(groups),
                }
    except AnagramError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        if payload["mode"] == "check":
            verdict = "anagrams" if payload["anagrams"] else "not anagrams"
            print(f"  {payload['first']!r} vs {payload['second']!r}: {verdict}")
            print(f"  signatures: {payload['first_signature']!r} / "
                  f"{payload['second_signature']!r}")
        elif payload["mode"] == "find":
            print(f"  {len(payload['matches'])} match(es) for "
                  f"{payload['word']!r}: {', '.join(payload['matches']) or '-'}")
        elif payload["mode"] == "pairs":
            print(f"  {payload['words']} words")
            print(render_pairs([tuple(pair) for pair in payload["pairs"]]))
        else:
            print(f"  {payload['words']} words")
            print(render_groups(payload["groups"]))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
