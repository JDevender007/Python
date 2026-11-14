"""Command line interface for the library.

    python src/main.py --demo
    python src/main.py                                     # every title
    python src/main.py --search crockford
    python src/main.py --available 9780132350884
    python src/main.py --member M-01
    python src/main.py --borrow 9780306406157:M-03:2026-03-10
    python src/main.py --return 9780306406157:M-03:2026-03-12
    python src/main.py --overdue --on 2026-03-10
    python src/main.py --fines --on 2026-03-10
    python src/main.py --add-book 9780262033848:CLRS:Thomas Cormen:2
    python src/main.py --copies 9780132350884:4
    python src/main.py --consistency
    python src/main.py --legacy
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from library import (
    DATA_FILE,
    LEGACY_ISBN,
    LEGACY_ISSUED,
    LEGACY_SHARED,
    LOAN_DAYS,
    Book,
    Library,
    LibraryError,
    load_library,
    money,
    run_demo,
    save_library,
)

BANNER = """
========================================
 RIVERSIDE LIBRARY
   loans counted, never stored twice
========================================
"""

TODAY = "2026-03-10"


def _split(spec: str, parts: int, shape: str) -> list[str]:
    pieces = [piece.strip() for piece in spec.split(":")]
    if len(pieces) != parts or not all(pieces):
        raise LibraryError(f"expected {shape}, got {spec!r}")
    return pieces


def _count(text: str) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        raise LibraryError(f"{text!r} is not a whole number") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A library whose availability is computed, not stored.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="library file (default: data/library.json)")
    parser.add_argument("--books", action="store_true",
                        help="one line per title (the default)")
    parser.add_argument("--search", metavar="TEXT",
                        help="titles whose ISBN, title or author matches")
    parser.add_argument("--available", metavar="ISBN",
                        help="copies owned, on loan and on the shelf")
    parser.add_argument("--member", metavar="ID", help="a member's open loans")
    parser.add_argument("--borrow", metavar="ISBN:MEMBER:DATE",
                        help="lend a copy")
    parser.add_argument("--return", dest="give_back",
                        metavar="ISBN:MEMBER:DATE", help="take a copy back")
    parser.add_argument("--overdue", action="store_true",
                        help="open loans past their due date")
    parser.add_argument("--fines", action="store_true",
                        help="what each member owes")
    parser.add_argument("--on", metavar="YYYY-MM-DD", default=TODAY,
                        help=f"the date to judge loans by (default {TODAY})")
    parser.add_argument("--add-book", metavar="ISBN:TITLE:AUTHOR:COPIES",
                        dest="add_book", help="put a new title on the shelf")
    parser.add_argument("--copies", metavar="ISBN:N",
                        help="change how many copies the library owns")
    parser.add_argument("--consistency", action="store_true",
                        help="run the five invariants")
    parser.add_argument("--legacy", action="store_true",
                        help="show the legacy defects the demo proves")
    parser.add_argument("--write", type=Path, metavar="PATH",
                        help="save the library after the change")
    parser.add_argument("--json", type=Path, metavar="PATH",
                        help="write the result as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="write no standard output")
    args = parser.parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo()
        else:
            run_demo()
        return 0

    try:
        if args.legacy:
            payload = {
                "mode": "legacy",
                "isbn": LEGACY_ISBN,
                "issued": LEGACY_ISSUED,
                "shared": LEGACY_SHARED,
                "note": "the clamp max(quantity - issued, 0) loses a copy",
            }
            if not args.quiet:
                print(BANNER)
                print(f"  isbn    {LEGACY_ISBN}")
                print(f"  issued  {LEGACY_ISSUED}   (a stored copy of a fact)")
                print(f"  shared  {LEGACY_SHARED}   (one list per class)")
                print(f"  {payload['note']}")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        library = load_library(args.file)
        payload: dict = {"mode": "books", "library": library.name,
                         "titles": len(library),
                         "copies": library.total_copies}

        if args.search is not None:
            found = library.search(args.search)
            payload = {"mode": "search", "needle": args.search,
                       "found": [book.isbn for book in found],
                       "count": len(found)}
            if not args.quiet:
                print(BANNER)
                for book in found:
                    print(f"  {book}  {library.available(book.isbn)} on the "
                          f"shelf")
                print(f"\n  {len(found)} title(s) match {args.search!r}")
        elif args.available is not None:
            book = library.book(args.available)
            on_loan = library.on_loan(book.isbn)
            payload = {"mode": "available", "isbn": book.isbn,
                       "title": book.title, "copies": book.copies,
                       "on_loan": on_loan,
                       "available": book.copies - on_loan,
                       "issued": library.issued(book.isbn)}
            if not args.quiet:
                print(BANNER)
                print(f"  {book.title}  by {book.author}")
                print(f"  {book.isbn}  {book.copies} owned, {on_loan} out, "
                      f"{book.copies - on_loan} on the shelf")
        elif args.member is not None:
            member = library.member(args.member)
            held = library.open_loans_of(member.member_id)
            payload = {"mode": "member", "member_id": member.member_id,
                       "name": member.name, "limit": member.limit,
                       "open": [{"isbn": loan.isbn,
                                 "due": loan.due.isoformat()}
                                for loan in held]}
            if not args.quiet:
                print(BANNER)
                print(f"  {member.member_id}  {member.name}  "
                      f"{len(held)} of {member.limit} allowed")
                for loan in held:
                    print(f"  {loan}")
        elif args.borrow is not None:
            isbn, member_id, day = _split(args.borrow, 3,
                                          "ISBN:MEMBER:YYYY-MM-DD")
            loan = library.borrow(isbn, member_id, day)
            payload = {"mode": "borrow", "isbn": loan.isbn,
                       "member_id": loan.member_id,
                       "borrowed": loan.borrowed.isoformat(),
                       "due": loan.due.isoformat()}
            if not args.quiet:
                print(BANNER)
                print(f"  {loan.isbn} -> {loan.member_id}")
                print(f"  borrowed {loan.borrowed.isoformat()}, due "
                      f"{loan.due.isoformat()} ({LOAN_DAYS} days)")
        elif args.give_back is not None:
            isbn, member_id, day = _split(args.give_back, 3,
                                          "ISBN:MEMBER:YYYY-MM-DD")
            loan, fine = library.give_back(isbn, member_id, day)
            payload = {"mode": "return", "isbn": loan.isbn,
                       "member_id": loan.member_id,
                       "returned": loan.returned.isoformat(),
                       "days_late": loan.days_late(),
                       "fine_cents": fine}
            if not args.quiet:
                print(BANNER)
                print(f"  {loan.isbn} from {loan.member_id} on "
                      f"{loan.returned.isoformat()}")
                print(f"  {loan.days_late()} day(s) late, fine "
                      f"{money(fine)}")
        elif args.overdue:
            late = library.overdue(args.on)
            payload = {"mode": "overdue", "on": args.on,
                       "loans": [{"isbn": loan.isbn,
                                  "member_id": loan.member_id,
                                  "due": loan.due.isoformat(),
                                  "days_late": loan.days_late(args.on),
                                  "fine_cents": loan.fine(args.on)}
                                 for loan in late],
                       "count": len(late),
                       "total_cents": library.total_fine(args.on)}
            if not args.quiet:
                print(BANNER)
                for loan in late:
                    print(f"  {loan.isbn}  {loan.member_id}  due "
                          f"{loan.due.isoformat()}  "
                          f"{loan.days_late(args.on)} day(s) late  "
                          f"{money(loan.fine(args.on))}")
                print(f"\n  {len(late)} overdue, "
                      f"{money(library.total_fine(args.on))} owed")
        elif args.fines:
            owed = library.fines(args.on)
            payload = {"mode": "fines", "on": args.on, "fines": owed,
                       "total_cents": sum(owed.values())}
            if not args.quiet:
                print(BANNER)
                for member_id, cents in owed.items():
                    print(f"  {member_id:<6} {money(cents):>10}")
                print(f"  {'total':<6} {money(sum(owed.values())):>10}")
        elif args.add_book is not None:
            isbn, title, author, copies = _split(
                args.add_book, 4, "ISBN:TITLE:AUTHOR:COPIES")
            book = library.add_book(Book(isbn, title, author,
                                         _count(copies)))
            payload = {"mode": "add_book", "isbn": book.isbn,
                       "title": book.title, "copies": book.copies}
            if not args.quiet:
                print(BANNER)
                print(f"  added {book.isbn}  {book.title}  x{book.copies}")
        elif args.copies is not None:
            isbn, count = _split(args.copies, 2, "ISBN:N")
            book = library.set_copies(isbn, _count(count))
            payload = {"mode": "copies", "isbn": book.isbn,
                       "copies": book.copies,
                       "on_loan": library.on_loan(book.isbn)}
            if not args.quiet:
                print(BANNER)
                print(f"  {book.isbn} now owns {book.copies} copies, "
                      f"{library.on_loan(book.isbn)} on loan")
        elif args.consistency:
            checks = library.consistency()
            payload = {"mode": "consistency",
                       "checks": [{"name": name, "passed": passed}
                                  for name, passed in checks],
                       "clean": all(passed for _, passed in checks)}
            if not args.quiet:
                print(BANNER)
                for name, passed in checks:
                    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
                print(f"\n  {sum(1 for _, ok in checks if ok)}/{len(checks)} "
                      f"checks passed")
        else:
            payload = {"mode": "books",
                       "books": [{"isbn": book.isbn, "title": book.title,
                                  "author": book.author,
                                  "copies": book.copies,
                                  "available": library.available(book.isbn)}
                                 for book in library]}
            if not args.quiet:
                print(BANNER)
                for book in library:
                    print(f"  {book}  "
                          f"{library.available(book.isbn):>2} on the shelf")
                print(f"\n  {len(library)} titles, {library.total_copies} "
                      f"copies, {len(library.open_loans)} on loan")

        if args.write:
            save_library(args.write, library)
            payload["written"] = args.write.name
            if not args.quiet:
                print(f"\n  written to {payload['written']}")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except LibraryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
