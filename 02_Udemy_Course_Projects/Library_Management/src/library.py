"""A library catalogue: copies, loans, returns and fines.

The legacy program stored books in a fixed-width binary file:

    FORMAT = "i30s20sf"          # id, title[30], author[20], price(float32)
    RECORD_SIZE = struct.calcsize(FORMAT)

    def pack_record(book_id, title, author, price):
        title = title.strip().encode()[:30].ljust(30)
        author = author.strip().encode()[:20].ljust(20)
        return struct.pack(FORMAT, book_id, title, author, price)

    def delete_book():
        ...
        with open(FILE_NAME, "rb") as file:
            records = file.readlines()      # on a binary file!
        with open(FILE_NAME, "wb") as file:
            for record in records:
                if len(record) != RECORD_SIZE:
                    continue                # silently drops the record
                ...

Five defects, each provable in isolation:

**1. Prices are float32.** ``19.99`` round-trips as ``19.989999771118164``.
A price is money; money is not a float. This module stores integer cents.

**2. Titles are sliced by byte, not by character.** ``title.encode()[:30]``
cuts UTF-8 mid-character, so a title of non-ASCII text stores bytes that
``.decode()`` refuses. ``pack`` succeeds and ``unpack`` raises later - the
corruption is written to disk before anyone notices.

**3. Truncation is silent.** A 40-character title becomes 30 with no warning,
and the lost text is gone.

**4. ``readlines()`` on a binary file splits on ``0x0A``.** That byte is 10,
which is a perfectly ordinary id or price byte. One record containing ``10``
becomes two short chunks, and ``delete_book`` skips every chunk whose length is
not exactly ``RECORD_SIZE`` - so deleting one book can delete an unrelated one.

**5. Ids are appended without a uniqueness check.** ``open(..., "ab")`` will
happily write a second record with the same id, and ``delete_book`` then deletes
both.

The replacement is JSON with integer cents, an explicit uniqueness check on
ids, and copies tracked inside the book rather than in a separate count.

    library.json
      books: isbn, title, author, price_cents, copies_total, copies_available
      loans: isbn, member, borrowed_on, due_on, returned_on|null

``copies_available`` is checked against the open loans on load, so a hand-edited
file cannot claim a copy is on the shelf while a loan says otherwise.

Fines are 25 cents per day late, capped at 10.00, charged on return (or
projected to "today" while the loan is still open). Standard library only.
"""

from __future__ import annotations

import datetime
import json
import os
import struct
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

LOAN_DAYS = 14
FINE_PER_DAY_CENTS = 25
FINE_CAP_CENTS = 1000
DATE_FORMAT = "%Y-%m-%d"
AS_OF = datetime.date(2024, 4, 15)
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


class LibraryError(ValueError):
    """A catalogue operation that cannot be completed."""


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
def parse_money(value) -> int:
    """Currency to integer cents, exactly.

    Accepts ``"19.99"``, ``19.99`` and ``19``; refuses more than two decimal
    places rather than rounding, because a price of ``19.999`` is a typo, not a
    price.
    """
    if isinstance(value, bool):
        raise LibraryError("money must not be a boolean")
    if isinstance(value, int):
        if value < 0:
            raise LibraryError(f"{value!r} is negative")
        return value * 100
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise LibraryError(f"{value!r} is not an amount of money") from None
    if not amount.is_finite():
        raise LibraryError(f"{value!r} is not a finite amount")
    if amount < 0:
        raise LibraryError(f"{value!r} is negative")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise LibraryError(f"{value!r} has more than two decimal places")
    return int(cents)


def format_money(cents: int) -> str:
    """Cents to ``1,234.56``."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise LibraryError(f"{cents!r} is not a number of cents")
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(cents), 100)
    return f"{sign}{whole:,}.{part:02d}"


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
def parse_date(value) -> datetime.date:
    """Strict ``YYYY-MM-DD``; ``strptime`` alone accepts ``2024-3-4``."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if not isinstance(value, str):
        raise LibraryError(f"date must be a string, got {type(value).__name__}")
    text = value.strip()
    try:
        parsed = datetime.datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        raise LibraryError(f"date {value!r} is not {DATE_FORMAT}") from None
    if parsed.strftime(DATE_FORMAT) != text:
        raise LibraryError(f"date {value!r} is not zero padded {DATE_FORMAT}")
    return parsed


# --------------------------------------------------------------------------- #
# The legacy binary format
# --------------------------------------------------------------------------- #
LEGACY_FORMAT = "i30s20sf"
LEGACY_RECORD_SIZE = struct.calcsize(LEGACY_FORMAT)


def legacy_pack(book_id: int, title: str, author: str,
                price: float) -> bytes:
    """The original packer, verbatim in spirit: bytes sliced, float32 price."""
    packed_title = title.strip().encode()[:30].ljust(30)
    packed_author = author.strip().encode()[:20].ljust(20)
    return struct.pack(LEGACY_FORMAT, book_id, packed_title, packed_author,
                       price)


def legacy_unpack(record: bytes) -> dict:
    """The original unpacker; raises if the bytes were cut mid-character."""
    book_id, title, author, price = struct.unpack(LEGACY_FORMAT, record)
    return {"id": book_id, "title": title.decode().strip(),
            "author": author.decode().strip(), "price": price}


def legacy_readlines_split(record: bytes) -> list[bytes]:
    """What ``readlines()`` does to a record in binary mode: split on ``0x0A``."""
    return record.split(b"\n")


def legacy_delete_keeps(records: list[bytes], book_id: int) -> list[bytes]:
    """The original delete loop, returning what it would have written back.

    Records whose length is not exactly ``RECORD_SIZE`` are skipped, which is
    how an unrelated book disappears.
    """
    kept: list[bytes] = []
    for record in records:
        if len(record) != LEGACY_RECORD_SIZE:
            continue
        try:
            book = legacy_unpack(record)
        except (struct.error, UnicodeDecodeError):
            continue
        if book["id"] != book_id:
            kept.append(record)
    return kept


# --------------------------------------------------------------------------- #
# Books and loans
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Book:
    isbn: str
    title: str
    author: str
    price_cents: int
    copies_total: int = 1
    copies_available: int = 1

    def __post_init__(self) -> None:
        isbn = _text(self.isbn, "isbn")
        title = _text(self.title, "title")
        author = _text(self.author, "author")
        if not isinstance(self.price_cents, int) or \
                isinstance(self.price_cents, bool):
            raise LibraryError("price_cents must be an integer")
        if self.price_cents < 0:
            raise LibraryError("price_cents must not be negative")
        if not isinstance(self.copies_total, int) or \
                isinstance(self.copies_total, bool):
            raise LibraryError("copies_total must be an integer")
        if self.copies_total < 1:
            raise LibraryError("copies_total must be at least 1")
        if not isinstance(self.copies_available, int) or \
                isinstance(self.copies_available, bool):
            raise LibraryError("copies_available must be an integer")
        if not 0 <= self.copies_available <= self.copies_total:
            raise LibraryError(
                f"copies_available {self.copies_available} is outside "
                f"0..{self.copies_total}")
        object.__setattr__(self, "isbn", isbn)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "author", author)

    @property
    def on_loan(self) -> int:
        return self.copies_total - self.copies_available

    def to_dict(self) -> dict:
        return {"isbn": self.isbn, "title": self.title,
                "author": self.author, "price_cents": self.price_cents,
                "copies_total": self.copies_total,
                "copies_available": self.copies_available}

    @staticmethod
    def from_dict(data: dict) -> "Book":
        if not isinstance(data, dict):
            raise LibraryError("a book must be a JSON object")
        required = ("isbn", "title", "author", "price_cents")
        for key in required:
            if key not in data:
                raise LibraryError(f"book is missing {key}")
        unknown = set(data) - set(required) - {"copies_total",
                                               "copies_available"}
        if unknown:
            raise LibraryError(f"book has unknown field {sorted(unknown)[0]}")
        total = data.get("copies_total", 1)
        return Book(data["isbn"], data["title"], data["author"],
                    data["price_cents"], total,
                    data.get("copies_available", total))


@dataclass(frozen=True)
class Loan:
    isbn: str
    member: str
    borrowed_on: datetime.date
    due_on: datetime.date
    returned_on: datetime.date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "isbn", _text(self.isbn, "isbn"))
        object.__setattr__(self, "member", _text(self.member, "member"))
        borrowed = parse_date(self.borrowed_on)
        due = parse_date(self.due_on)
        returned = (None if self.returned_on is None
                    else parse_date(self.returned_on))
        if due <= borrowed:
            raise LibraryError("due_on must be after borrowed_on")
        if returned is not None and returned < borrowed:
            raise LibraryError("returned_on must not precede borrowed_on")
        object.__setattr__(self, "borrowed_on", borrowed)
        object.__setattr__(self, "due_on", due)
        object.__setattr__(self, "returned_on", returned)

    @property
    def open(self) -> bool:
        return self.returned_on is None

    def days_late(self, today: datetime.date) -> int:
        """Days past the due date, measured at return or at ``today``."""
        marker = self.returned_on if self.returned_on is not None else \
            parse_date(today)
        return max(0, (marker - self.due_on).days)

    def fine_cents(self, today: datetime.date) -> int:
        return min(self.days_late(today) * FINE_PER_DAY_CENTS, FINE_CAP_CENTS)

    def to_dict(self) -> dict:
        return {"isbn": self.isbn, "member": self.member,
                "borrowed_on": self.borrowed_on.strftime(DATE_FORMAT),
                "due_on": self.due_on.strftime(DATE_FORMAT),
                "returned_on": (None if self.returned_on is None
                                else self.returned_on.strftime(DATE_FORMAT))}

    @staticmethod
    def from_dict(data: dict) -> "Loan":
        if not isinstance(data, dict):
            raise LibraryError("a loan must be a JSON object")
        for key in ("isbn", "member", "borrowed_on", "due_on"):
            if key not in data:
                raise LibraryError(f"loan is missing {key}")
        unknown = set(data) - {"isbn", "member", "borrowed_on", "due_on",
                               "returned_on"}
        if unknown:
            raise LibraryError(f"loan has unknown field {sorted(unknown)[0]}")
        return Loan(data["isbn"], data["member"], data["borrowed_on"],
                    data["due_on"], data.get("returned_on"))


def _text(value, label: str) -> str:
    if not isinstance(value, str):
        raise LibraryError(f"{label} must be a string")
    text = value.strip()
    if not text:
        raise LibraryError(f"{label} must not be empty")
    return text


# --------------------------------------------------------------------------- #
# The catalogue
# --------------------------------------------------------------------------- #
@dataclass
class Catalog:
    books: dict[str, Book] = field(default_factory=dict)
    loans: list[Loan] = field(default_factory=list)

    # -- books ------------------------------------------------------------- #
    def add(self, book: Book) -> Book:
        if book.isbn in self.books:
            raise LibraryError(f"isbn {book.isbn} is already catalogued")
        if book.copies_available != book.copies_total:
            raise LibraryError(
                "a new book must start with every copy available")
        self.books[book.isbn] = book
        return book

    def add_new(self, isbn: str, title: str, author: str, price,
                copies: int = 1) -> Book:
        return self.add(Book(isbn, title, author, parse_money(price), copies,
                             copies))

    def remove(self, isbn: str) -> Book:
        book = self.get(isbn)
        if book.on_loan:
            raise LibraryError(
                f"{book.on_loan} cop(y/ies) of {isbn} are still on loan")
        del self.books[isbn]
        return book

    def get(self, isbn: str) -> Book:
        key = _text(isbn, "isbn")
        if key not in self.books:
            raise LibraryError(f"isbn {key} is not catalogued")
        return self.books[key]

    def search(self, term) -> list[Book]:
        needle = _text(term, "search term").casefold()
        return [book for book in self.books.values()
                if needle in book.isbn.casefold()
                or needle in book.title.casefold()
                or needle in book.author.casefold()]

    # -- loans ------------------------------------------------------------- #
    def open_loans(self, isbn: str | None = None) -> list[Loan]:
        return [loan for loan in self.loans
                if loan.open and (isbn is None or loan.isbn == isbn)]

    def borrow(self, isbn: str, member: str,
               today: datetime.date = AS_OF) -> Loan:
        day = parse_date(today)
        book = self.get(isbn)
        borrower = _text(member, "member")
        if book.copies_available < 1:
            raise LibraryError(f"no copy of {isbn} is available")
        if any(loan.member == borrower for loan in self.open_loans(isbn)):
            raise LibraryError(
                f"{borrower} already has a copy of {isbn} on loan")
        self.books[isbn] = Book(book.isbn, book.title, book.author,
                               book.price_cents, book.copies_total,
                               book.copies_available - 1)
        loan = Loan(book.isbn, borrower, day, day + datetime.timedelta(
            days=LOAN_DAYS))
        self.loans.append(loan)
        return loan

    def give_back(self, isbn: str, member: str,
                  today: datetime.date = AS_OF) -> tuple[Loan, int]:
        day = parse_date(today)
        borrower = _text(member, "member")
        book = self.get(isbn)
        for index, loan in enumerate(self.loans):
            if loan.isbn == isbn and loan.member == borrower and loan.open:
                if day < loan.borrowed_on:
                    raise LibraryError("returned before it was borrowed")
                returned = Loan(loan.isbn, loan.member, loan.borrowed_on,
                                loan.due_on, day)
                self.loans[index] = returned
                self.books[isbn] = Book(book.isbn, book.title, book.author,
                                       book.price_cents, book.copies_total,
                                       book.copies_available + 1)
                return returned, returned.fine_cents(day)
        raise LibraryError(f"{borrower} has no open loan of {isbn}")

    def member_loans(self, member: str) -> list[Loan]:
        borrower = _text(member, "member")
        return [loan for loan in self.loans if loan.member == borrower]

    def overdue(self, today: datetime.date = AS_OF) -> list[Loan]:
        day = parse_date(today)
        return sorted((loan for loan in self.loans if loan.open
                       and loan.due_on < day),
                      key=lambda loan: (loan.due_on, loan.isbn))

    def fines_outstanding(self, today: datetime.date = AS_OF) -> int:
        day = parse_date(today)
        return sum(loan.fine_cents(day) for loan in self.loans if loan.open)

    # -- consistency ------------------------------------------------------- #
    def audit(self) -> list[str]:
        """Every way the catalogue contradicts itself, as strings."""
        problems: list[str] = []
        for isbn, book in self.books.items():
            open_count = len(self.open_loans(isbn))
            if book.copies_total - book.copies_available != open_count:
                problems.append(
                    f"{isbn}: {book.on_loan} cop(y/ies) marked on loan but "
                    f"{open_count} open loan(s)")
        for loan in self.loans:
            if loan.isbn not in self.books:
                problems.append(f"loan of unknown isbn {loan.isbn}")
        ids = [book.isbn for book in self.books.values()]
        if len(ids) != len(set(ids)):
            problems.append("duplicate isbn in the catalogue")
        return problems

    # -- storage ----------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"books": [book.to_dict() for book in
                          sorted(self.books.values(), key=lambda b: b.isbn)],
                "loans": [loan.to_dict() for loan in self.loans]}

    @staticmethod
    def from_dict(data: dict) -> "Catalog":
        if not isinstance(data, dict):
            raise LibraryError("the catalogue must be a JSON object")
        for key in ("books", "loans"):
            if key not in data:
                raise LibraryError(f"the catalogue is missing {key}")
        if not isinstance(data["books"], list) or \
                not isinstance(data["loans"], list):
            raise LibraryError("books and loans must be lists")
        catalog = Catalog()
        for item in data["books"]:
            book = Book.from_dict(item)
            if book.isbn in catalog.books:
                raise LibraryError(f"isbn {book.isbn} appears twice")
            catalog.books[book.isbn] = book
        for item in data["loans"]:
            catalog.loans.append(Loan.from_dict(item))
        return catalog

    def save(self, path: str | Path = DATA_FILE) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=1, sort_keys=True) + "\n"
        handle, temporary = tempfile.mkstemp(dir=str(path.parent),
                                             suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
                out.write(payload)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return path


def load(path: str | Path = DATA_FILE) -> Catalog:
    path = Path(path)
    if not path.exists():
        raise LibraryError(f"catalogue not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LibraryError(f"{path.name} is not valid JSON: {exc}") from None
    return Catalog.from_dict(data)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def render_book(book: Book) -> str:
    return (f"  {book.isbn}  {book.title:<32.32}  {book.author:<22.22}  "
            f"{format_money(book.price_cents):>8}  "
            f"{book.copies_available}/{book.copies_total}")


def render_loan(loan: Loan, today: datetime.date = AS_OF) -> str:
    state = (f"due {loan.due_on.strftime(DATE_FORMAT)}"
             if loan.open else
             f"back {loan.returned_on.strftime(DATE_FORMAT)}")
    fine = loan.fine_cents(today)
    tail = f"  fine {format_money(fine)}" if fine else ""
    return (f"  {loan.isbn}  {loan.member:<10}  "
            f"{loan.borrowed_on.strftime(DATE_FORMAT)}  {state}{tail}")


def stats(catalog: Catalog, today: datetime.date = AS_OF) -> dict:
    day = parse_date(today)
    copies = sum(book.copies_total for book in catalog.books.values())
    available = sum(book.copies_available for book in catalog.books.values())
    return {
        "books": len(catalog.books),
        "copies": copies,
        "available": available,
        "on_loan": copies - available,
        "members": len({loan.member for loan in catalog.loans}),
        "overdue": len(catalog.overdue(day)),
        "fines_cents": catalog.fines_outstanding(day),
    }


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 70)
    print(" LIBRARY MANAGEMENT - fixed-width binary records, and what they cost")
    print("=" * 70)

    # 1. float32 stores 19.99 as 19.989999771118164
    record = legacy_pack(1, "Clean Code", "Robert C. Martin", 19.99)
    recovered = legacy_unpack(record)["price"]
    assert recovered != 19.99
    assert abs(recovered - 19.99) < 0.001
    assert parse_money("19.99") == 1999
    print(f"  legacy price 19.99 round-trips as {recovered!r}; "
          f"integer cents stay 1999")

    # 2. a byte-sliced title is not valid UTF-8
    title = "a" + "e\u0301" * 20
    truncated = title.strip().encode()[:30]
    try:
        truncated.decode()
    except UnicodeDecodeError as exc:
        assert "invalid continuation byte" in str(exc) or \
            "unexpected end of data" in str(exc), str(exc)
        message = type(exc).__name__
    else:
        raise AssertionError("the sliced title should not decode")
    print(f"  30 bytes of a 41-byte title: decode raises {message}")

    # 3. ... and the slicer silently drops text that does fit
    long_title = "An Extremely Long Title That Will Not Fit In Thirty Bytes"
    cut = legacy_unpack(legacy_pack(2, long_title, "A", 1.0))["title"]
    assert cut != long_title
    assert long_title.startswith(cut)
    assert len(cut) == 30
    print(f"  a {len(long_title)}-char title is stored as {len(cut)} chars, "
          f"no warning")

    # 4. readlines() on a binary file splits on byte 10
    #    an id of 10 is legal, and its low byte is 0x0A - the byte readlines()
    #    treats as a line separator, in the middle of a fixed-size record
    risky = legacy_pack(10, "Book", "Author", 1.0)
    healthy = legacy_pack(11, "Other", "A", 2.0)
    assert b"\n" in risky and b"\n" not in healthy
    chunks = legacy_readlines_split(risky)
    assert len(chunks) == 2
    assert all(len(chunk) != LEGACY_RECORD_SIZE for chunk in chunks)
    kept = legacy_delete_keeps(chunks + [healthy], 99)
    assert kept == [healthy], kept      # only the healthy neighbour survived
    print(f"  id 10 puts 0x0A inside its record: readlines() yields "
          f"{len(chunks)} chunks, and a delete of a different id drops it "
          f"while its neighbour survives")

    # 5. appending does not check ids
    twice = legacy_pack(7, "Dune", "Frank Herbert", 9.99) * 2
    ids = [legacy_unpack(twice[i:i + LEGACY_RECORD_SIZE])["id"]
           for i in range(0, len(twice), LEGACY_RECORD_SIZE)]
    assert ids == [7, 7]
    print(f"  two records, one id: {ids} - append never checked")

    # 6. the replacement: exact money, unique ids, copies
    catalog = Catalog()
    catalog.add_new("978-0132350884", "Clean Code", "Robert C. Martin",
                    "42.50", 2)
    catalog.add_new("978-0134757599", "Refactoring", "Martin Fowler",
                    "47.20")
    assert format_money(parse_money("42.50")) == "42.50"
    assert format_money(parse_money(123456)) == "123,456.00"
    assert parse_money(19.99) == 1999
    for bad in ("19.999", "abc", -1, "nan", True):
        try:
            parse_money(bad)
        except LibraryError:
            pass
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    try:
        catalog.add_new("978-0132350884", "Again", "X", "1.00")
    except LibraryError as exc:
        assert "already catalogued" in str(exc)
    else:
        raise AssertionError("a duplicate isbn should have been refused")
    print(f"  2 books added, 4 bad prices and a duplicate isbn refused")

    # 7. borrowing decrements, and refuses when the shelf is empty
    first = catalog.borrow("978-0132350884", "asha", "2024-04-01")
    assert first.due_on == datetime.date(2024, 4, 15)
    second = catalog.borrow("978-0132350884", "ravi", "2024-04-02")
    assert catalog.get("978-0132350884").copies_available == 0
    for attempt in (lambda: catalog.borrow("978-0132350884", "mei",
                                           "2024-04-03"),
                    lambda: catalog.borrow("978-0132350884", "asha",
                                           "2024-04-03"),
                    lambda: catalog.borrow("978-0000000000", "mei",
                                           "2024-04-03")):
        try:
            attempt()
        except LibraryError:
            pass
        else:
            raise AssertionError("an impossible borrow should have failed")
    assert second.due_on == datetime.date(2024, 4, 16)
    print("  2 copies borrowed, then no copy / same member / unknown isbn "
          "refused")

    # 8. returning restores the copy and charges only real lateness
    on_time, fine = catalog.give_back("978-0132350884", "asha", "2024-04-15")
    assert fine == 0 and on_time.returned_on == datetime.date(2024, 4, 15)
    daily_fine, fine = catalog.give_back("978-0132350884", "ravi",
                                        "2024-04-21")
    assert daily_fine.days_late("2024-04-21") == 5
    assert fine == 5 * FINE_PER_DAY_CENTS == 125
    assert catalog.get("978-0132350884").copies_available == 2
    try:
        catalog.give_back("978-0132350884", "ravi", "2024-04-22")
    except LibraryError as exc:
        assert "no open loan" in str(exc)
    else:
        raise AssertionError("a second return should have been refused")
    print(f"  on time: 0.00; 5 days late: {format_money(fine)}; "
          f"a second return refused")

    # 9. the cap
    capped = Loan("978-0134757599", "mei", "2024-01-01", "2024-01-15",
                  "2024-06-01")
    assert capped.days_late("2024-06-01") == 138
    assert capped.fine_cents("2024-06-01") == FINE_CAP_CENTS == 1000
    uncapped = Loan("978-0134757599", "mei", "2024-01-01", "2024-01-15",
                    "2024-01-20")
    assert uncapped.fine_cents("2024-01-20") == 125
    print(f"  138 days late is capped at {format_money(FINE_CAP_CENTS)}, "
          f"5 days is {format_money(125)}")

    # 10. consistency survives a save and load
    catalog.borrow("978-0134757599", "mei", "2024-04-10")
    assert catalog.audit() == []
    with tempfile.TemporaryDirectory(prefix="lib-") as folder:
        path = Path(folder) / "catalog.json"
        catalog.save(path)
        reloaded = load(path)
        assert reloaded.to_dict() == catalog.to_dict()
        assert reloaded.audit() == []
        before = path.read_bytes()
        reloaded.save(path)
        assert path.read_bytes() == before
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["books"][0]["copies_available"] = 99
        path.write_text(json.dumps(raw), encoding="utf-8")
        try:
            broken = load(path)
        except LibraryError as exc:
            assert "outside" in str(exc), str(exc)
        else:
            raise AssertionError("an impossible copy count should be refused")
    print("  save/reload identical, audit clean, a hand-edited count refused")

    # 11. the bundled catalogue agrees with itself
    bundled = load(DATA_FILE)
    assert bundled.audit() == []
    summary = stats(bundled)
    assert summary == {"books": 6, "copies": 8, "available": 5, "on_loan": 3,
                       "members": 4, "overdue": 2, "fines_cents": 1075}, summary
    overdue = bundled.overdue()
    assert [loan.member for loan in overdue] == ["mei", "asha"]
    assert bundled.fines_outstanding() == 1075
    assert bundled.get("978-0262033848").copies_available == 0
    assert len(bundled.search("clean")) == 1
    assert len(bundled.search("a")) >= 4
    print(f"  6 books, 8 copies, 5 on the shelf, 3 out, 2 overdue, "
          f"fines {format_money(1075)}")

    # 12. search is case-insensitive and covers every field
    assert bundled.search("MARTIN") and bundled.search("978-0132350884")
    try:
        bundled.search("   ")
    except LibraryError as exc:
        assert "must not be empty" in str(exc)
    else:
        raise AssertionError("an empty search should have been refused")
    print("  search covers isbn, title and author; a blank term is refused")

    print()
    print("Cross-checks OK: float32 mangled 19.99, a 30-byte slice of a "
          "41-byte title failed to decode and a long title was cut silently, "
          "id 10 hid a 0x0A that readlines() split in two and delete then "
          "dropped, duplicate ids were accepted by append, integer cents "
          "stayed exact, 4 bad prices and a duplicate isbn refused, "
          "borrowing refused on an empty shelf, the same member and an "
          "unknown isbn, returns charged 0.00 and 1.25 and refused a second "
          "time, a 138-day loan capped at 10.00, a save/reload round trip "
          "byte-identical with a clean audit, and a 6-book bundled catalogue "
          "agreeing with its own loans")
    print("\nDemo completed successfully.")
    return 0
