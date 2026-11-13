"""Command line entry point for the contact book.

Usage
-----
    python src/main.py --demo                      # self-checking demo
    python src/main.py                             # list the bundled book
    python src/main.py --search "ana"
    python src/main.py --search "ana" --tag work
    python src/main.py --add "Gita Patel|gita@example.com|+44 20 7946 0000"
    python src/main.py --export-csv out/contacts.csv
    python src/main.py --merge other.json --policy prefer-incoming
    python src/main.py --json out.json --quiet

The book is loaded from ``data/contacts.json`` (or ``--file``), mutated in
memory, and written back only when you ask with ``--save``.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from contacts import (
    ContactBook,
    ContactError,
    ConflictError,
    run_demo,
)

BANNER = """
====================================
 CONTACT BOOK
   validate, search, merge, export
====================================
"""

DEFAULT_FILE = (Path(__file__).resolve().parent.parent
                / "data" / "contacts.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A validated address book with search, merge and "
                    "CSV/JSON export (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=None,
                        help="contacts JSON to load (default: the bundled one)")
    parser.add_argument("--search", metavar="TEXT", default=None,
                        help="match every whitespace-separated term")
    parser.add_argument("--tag", metavar="TAG", default=None,
                        help="keep only contacts carrying this tag")
    parser.add_argument("--company", metavar="TEXT", default=None,
                        help="keep only contacts whose company matches")
    parser.add_argument("--add", metavar="NAME|EMAIL|PHONE", default=None,
                        help="add a contact from a pipe-separated triple")
    parser.add_argument("--merge", type=Path, default=None,
                        help="merge another contacts JSON file into the book")
    parser.add_argument("--policy", choices=("prefer-existing",
                                             "prefer-incoming"),
                        default="prefer-existing",
                        help="which side wins on a duplicate email")
    parser.add_argument("--export-csv", type=Path, default=None,
                        help="write the book as CSV")
    parser.add_argument("--save", type=Path, default=None,
                        help="write the book back as JSON")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the listed contacts as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def parse_add(spec: str):
    """Split ``NAME|EMAIL|PHONE``; every part is required."""
    parts = [part.strip() for part in spec.split("|")]
    if len(parts) != 3 or not all(parts):
        raise ContactError(
            "--add needs NAME|EMAIL|PHONE, all three non-empty")
    return parts


def render(contacts) -> str:
    lines = [f"  {'id':<7}{'name':<20}{'phone':<17}{'tags'}",
             "  " + "-" * 62]
    for contact in contacts:
        lines.append(
            f"  {contact.id:<7}{contact.name[:19]:<20}"
            f"{contact.phone:<17}{','.join(contact.tags)}")
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
        except ContactError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        book = ContactBook.load(args.file or DEFAULT_FILE)
        added = None
        if args.add:
            name, email, phone = parse_add(args.add)
            added = book.create(name, email, phone)
        report = None
        if args.merge:
            report = book.merge(ContactBook.load(args.merge), args.policy)
        contacts = book.search(args.search or "", tag=args.tag,
                               company=args.company)
    except (ContactError, ConflictError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(render(contacts))
        print(f"\n{len(contacts)} of {len(book)} contacts")
        if added is not None:
            print(f"Added {added.id} ({added.email})")
        if report is not None:
            print(f"Merge: {report}")

    if args.export_csv:
        book.export_csv(args.export_csv)
        if not args.quiet:
            print(f"Wrote {args.export_csv}")
    if args.save:
        book.save(args.save)
        if not args.quiet:
            print(f"Saved {args.save}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps([contact.to_dict() for contact in contacts], indent=2),
            encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
