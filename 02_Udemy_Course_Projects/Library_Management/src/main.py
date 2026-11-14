"""Command line interface for the library catalogue.

    python src/main.py --demo
    python src/main.py                       # the bundled catalogue
    python src/main.py --stats
    python src/main.py --overdue
    python src/main.py --search clean
    python src/main.py --borrow 978-0132350884:asha --today 2024-04-16
    python src/main.py --return 978-0132350884:asha --today 2024-04-30
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from library import (
    AS_OF,
    DATA_FILE,
    LEGACY_RECORD_SIZE,
    Catalog,
    LibraryError,
    format_money,
    legacy_pack,
    legacy_readlines_split,
    legacy_unpack,
    load,
    parse_date,
    parse_money,
    render_book,
    render_loan,
    run_demo,
    stats,
)

BANNER = """
====================================
 LIBRARY MANAGEMENT
   copies, loans, fines
====================================
"""


def _split_pair(value: str, separator: str = ":") -> tuple[str, str]:
    if separator not in value:
        raise LibraryError(f"expected ISBN{separator}MEMBER, got {value!r}")
    left, right = value.split(separator, 1)
    return left.strip(), right.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Catalogue copies, loans and fines.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--legacy", action="store_true",
                        help="show the three legacy format defects")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="catalogue file (default: data/catalog.json)")
    parser.add_argument("--today", default=AS_OF.strftime("%Y-%m-%d"),
                        help="the date loans and fines are measured against")
    parser.add_argument("--list", action="store_true",
                        help="list every book (the default mode)")
    parser.add_argument("--search", metavar="TERM",
                        help="match isbn, title or author")
    parser.add_argument("--loans", metavar="MEMBER",
                        help="loans belonging to one member")
    parser.add_argument("--overdue", action="store_true",
                        help="open loans past their due date")
    parser.add_argument("--stats", action="store_true",
                        help="counts, overdue totals and outstanding fines")
    parser.add_argument("--borrow", metavar="ISBN:MEMBER",
                        help="lend one copy")
    parser.add_argument("--return", metavar="ISBN:MEMBER", dest="give_back",
                        help="take one copy back and charge any fine")
    parser.add_argument("--write", action="store_true",
                        help="save the catalogue after a borrow or return")
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
        today = parse_date(args.today)

        if args.legacy:
            record = legacy_pack(1, "Clean Code", "Robert C. Martin", 19.99)
            title = "a" + "e\u0301" * 20
            sliced = title.strip().encode()[:30]
            try:
                sliced.decode()
            except UnicodeDecodeError as exc:
                cut_error = str(exc)
            else:                                        # pragma: no cover
                cut_error = ""
            risky = legacy_pack(10, "Book", "Author", 1.0)
            payload = {
                "mode": "legacy",
                "record_size": LEGACY_RECORD_SIZE,
                "price_round_trip": legacy_unpack(record)["price"],
                "price_cents": parse_money("19.99"),
                "slice_error": cut_error,
                "chunks": len(legacy_readlines_split(risky)),
            }
            if not args.quiet:
                print(BANNER)
                print(f"  record size        {payload['record_size']} bytes")
                print(f"  price 19.99        stored as "
                      f"{payload['price_round_trip']!r}")
                print(f"  integer cents      {payload['price_cents']}")
                print(f"  30-byte title      {cut_error}")
                print(f"  id 10 in readlines {payload['chunks']} chunks")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        catalog = load(args.file)
        payload: dict = {"today": today.strftime("%Y-%m-%d"),
                         "file": args.file.name}

        if args.borrow:
            isbn, member = _split_pair(args.borrow)
            loan = catalog.borrow(isbn, member, today)
            payload.update({"mode": "borrow", "loan": loan.to_dict()})
        elif args.give_back:
            isbn, member = _split_pair(args.give_back)
            loan, fine = catalog.give_back(isbn, member, today)
            payload.update({"mode": "return", "loan": loan.to_dict(),
                            "fine_cents": fine,
                            "fine": format_money(fine)})
        elif args.search:
            matches = catalog.search(args.search)
            payload.update({"mode": "search",
                            "books": [book.to_dict() for book in matches],
                            "count": len(matches)})
        elif args.loans:
            loans = catalog.member_loans(args.loans)
            payload.update({"mode": "loans",
                            "loans": [loan.to_dict() for loan in loans],
                            "count": len(loans)})
        elif args.overdue:
            loans = catalog.overdue(today)
            payload.update({"mode": "overdue",
                            "loans": [loan.to_dict() for loan in loans],
                            "count": len(loans),
                            "fines_cents": catalog.fines_outstanding(today)})
        elif args.stats:
            payload.update({"mode": "stats", "stats": stats(catalog, today)})
        else:
            payload.update({"mode": "list", "books": catalog.to_dict()["books"],
                            "loans": [loan.to_dict() for loan in
                                      catalog.open_loans()],
                            "stats": stats(catalog, today)})

        if args.write and payload["mode"] in ("borrow", "return"):
            catalog.save(args.file)
            payload["written"] = args.file.name

        if not args.quiet:
            print(BANNER)
            if payload["mode"] == "borrow":
                print(render_loan(catalog.loans[-1], today))
            elif payload["mode"] == "return":
                print(render_loan(catalog.loans[-1], today))
                print(f"\n  fine {payload['fine']}")
            elif payload["mode"] in ("search", "list"):
                books = payload["books"]
                if books:
                    print("  isbn/TITLE/AUTHOR                 "
                          "PRICE     AVAIL")
                    for book in books:
                        from library import Book
                        print(render_book(Book.from_dict(book)))
                else:
                    print("  (no books)")
            elif payload["mode"] in ("loans", "overdue"):
                loans = payload["loans"]
                if loans:
                    for loan in loans:
                        from library import Loan
                        print(render_loan(Loan.from_dict(loan), today))
                else:
                    print("  (no loans)")
                if payload["mode"] == "overdue":
                    print(f"\n  fines outstanding "
                          f"{format_money(payload['fines_cents'])}")
            if payload["mode"] in ("list", "stats"):
                summary = payload["stats"]
                print(f"\n  {summary['books']} book(s), "
                      f"{summary['copies']} cop(y/ies), "
                      f"{summary['available']} available, "
                      f"{summary['on_loan']} on loan")
                print(f"  {summary['overdue']} overdue, fines "
                      f"{format_money(summary['fines_cents'])}, "
                      f"{summary['members']} member(s)")
            if args.write and payload.get("written"):
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
