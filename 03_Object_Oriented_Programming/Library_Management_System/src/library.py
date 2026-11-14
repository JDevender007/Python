"""A library where the number on loan is counted, never stored twice.

The legacy project was SQLAlchemy over SQLite:

    class Book(Base):
        quantity = Column(Integer, nullable=False)
        available = Column(Integer, nullable=False)
        issued = Column(Boolean, default=False)

    def issue_book(self, book_id):
        book.available -= 1
        if book.available != book.quantity:
            book.issued = True

    def return_book(self, book_id):
        book.available += 1
        if book.available == book.quantity:
            book.issued = False

    def update_book(self, book_id, title, author, isbn, quantity):
        issued = book.quantity - book.available
        book.quantity = quantity
        book.available = max(quantity - issued, 0)

Two numbers describe one fact -- how many copies are out -- and a third is a
boolean derived from them. Nothing keeps them in agreement.

**1. `issued` is a stored copy of a derivable fact.** It is recomputed on every
issue and return, so it is only as correct as the last write. ``issued`` here is
a method that counts open loans; there is no column to fall out of date.

**2. `max(quantity - issued, 0)` silently destroys information.** A library that
owns five copies and has four out, then "corrects" the quantity to three, is
clamped to ``available = max(3 - 4, 0) = 0``. Four copies are still out but the
record can only account for three, and every later return keeps the record one
copy behind. ``Library.set_copies`` refuses the shrink instead, naming the loans
that would be broken.

**3. `available` is unchecked.** Any integer can be written into the column, so
``available > quantity`` and negative copies are both storable. Here ``copies``
is a property with a validating setter, and ``available`` is computed as
``copies - open_loans``, so it cannot disagree with the shelf.

**4. `len(value.strip()) >= 5` was the ISBN check.** ``abcde`` passed. This
project validates the real ISBN-10 and ISBN-13 checksums and normalises hyphens
and spaces away.

The lesson beyond the ledger is the class attribute:

    class LibraryService:
        books = []          # one list, shared by every instance

An instance that appends to ``books`` changes every other instance's books,
because attribute lookup finds the class object first. ``shared_shelf`` in this
module reproduces that bug on purpose; ``Library`` gives every instance its own
dictionaries in ``__init__``.

Standard library only: no ORM, no database file, no network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "library.json"

#: The legacy ISBN test: five characters was enough.
LEGACY_ISBN = "return len(value.strip()) >= 5"

#: The legacy derived flag, stored in a column.
LEGACY_ISSUED = "issued = Column(Boolean, default=False)"

#: The legacy shared class attribute.
LEGACY_SHARED = "books = []"

#: How long a loan runs, in days.
LOAN_DAYS = 14

#: The fine for one late day, in cents.
FINE_PER_DAY = 25


class LibraryError(ValueError):
    """A book, a member, a loan or a data file that cannot be accepted."""


class DuplicateBook(LibraryError):
    """The ISBN is already on the shelf."""


class DuplicateMember(LibraryError):
    """The member id is already registered."""


class NoCopiesLeft(LibraryError):
    """Every copy of the book is already out."""


class LoanLimitReached(LibraryError):
    """The member already holds as many books as their limit allows."""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def as_date(value, label: str = "a date") -> date:
    """A strict ISO date: ``2026-3-2`` is refused as well as ``2026-02-30``."""
    if isinstance(value, datetime):
        raise LibraryError(f"{label} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or isinstance(value, bool):
        raise LibraryError(f"{label} must be a date as YYYY-MM-DD, got "
                           f"{type(value).__name__}")
    text = value.strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        raise LibraryError(f"{text!r} is not a real date (YYYY-MM-DD)") \
            from None
    if parsed.isoformat() != text:
        raise LibraryError(f"{text!r} is not a canonical date (YYYY-MM-DD)")
    return parsed


def check_whole(value, label: str = "a count") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LibraryError(f"{label} must be a whole number, got "
                           f"{type(value).__name__}")
    if value < 0:
        raise LibraryError(f"{label} must not be negative")
    return value


def money(cents: int) -> str:
    """``25`` -> ``Rs 0.25``; the only place a fine becomes text."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise LibraryError("only an integer number of cents can be shown")
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}Rs {whole:,}.{fraction:02d}"


# --------------------------------------------------------------------------- #
# ISBNs: the real checksums
# --------------------------------------------------------------------------- #
def normalise_isbn(value) -> str:
    """Strip hyphens and spaces, upper-case, then prove the checksum."""
    if not isinstance(value, str):
        raise LibraryError(f"an ISBN must be text, got "
                           f"{type(value).__name__}")
    cleaned = value.replace("-", "").replace(" ", "").strip().upper()
    if not cleaned:
        raise LibraryError("an ISBN must not be empty")
    if not isbn_is_valid(cleaned):
        raise LibraryError(f"{value!r} is not a valid ISBN-10 or ISBN-13")
    return cleaned


def isbn_is_valid(value) -> bool:
    """True for a ten or thirteen digit ISBN whose check digit agrees."""
    if not isinstance(value, str):
        return False
    text = value.replace("-", "").replace(" ", "").strip().upper()
    if len(text) == 10:
        if not text[:9].isdigit() or not (text[9].isdigit() or text[9] == "X"):
            return False
        total = sum((10 - index) * (10 if digit == "X" else int(digit))
                    for index, digit in enumerate(text))
        return total % 11 == 0
    if len(text) == 13:
        if not text.isdigit():
            return False
        total = sum(int(digit) * (3 if index % 2 else 1)
                    for index, digit in enumerate(text))
        return total % 10 == 0
    return False


def isbn_kind(value) -> int:
    """10 or 13, once the ISBN has been validated."""
    return len(normalise_isbn(value))


def legacy_isbn_ok(value) -> bool:
    """The legacy test, transcribed: five characters was enough."""
    return len(value.strip()) >= 5


# --------------------------------------------------------------------------- #
# Member
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Member:
    """A reader: an id, a name and how many books they may hold at once."""

    member_id: str
    name: str
    limit: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.member_id, str) or not self.member_id.strip():
            raise LibraryError("a member needs an id")
        if not isinstance(self.name, str) or not self.name.strip():
            raise LibraryError("a member needs a name")
        if isinstance(self.limit, bool) or not isinstance(self.limit, int):
            raise LibraryError("a loan limit must be a whole number")
        if self.limit < 1:
            raise LibraryError("a loan limit must be at least one")

    def to_dict(self) -> dict:
        return {"member_id": self.member_id.strip(), "name": self.name.strip(),
                "limit": self.limit}

    @classmethod
    def from_dict(cls, row) -> "Member":
        if not isinstance(row, dict):
            raise LibraryError("a member must be an object")
        unknown = set(row) - {"member_id", "name", "limit"}
        if unknown:
            raise LibraryError(f"unknown member keys: {sorted(unknown)}")
        for key in ("member_id", "name"):
            if key not in row:
                raise LibraryError(f"a member is missing {key!r}")
        return cls(row["member_id"], row["name"], row.get("limit", 3))


# --------------------------------------------------------------------------- #
# Loan: a value, and the due date is derived from the borrow date
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Loan:
    """One book, one member, a borrow date, a due date, maybe a return date."""

    isbn: str
    member_id: str
    borrowed: date
    due: date
    returned: date | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.isbn, str) or not self.isbn.strip():
            raise LibraryError("a loan needs an ISBN")
        if not isinstance(self.member_id, str) or not self.member_id.strip():
            raise LibraryError("a loan needs a member id")
        if not isinstance(self.borrowed, date) or \
                isinstance(self.borrowed, datetime):
            raise LibraryError("a loan needs a borrow date")
        if not isinstance(self.due, date) or isinstance(self.due, datetime):
            raise LibraryError("a loan needs a due date")
        if self.due != self.borrowed + timedelta(days=LOAN_DAYS):
            raise LibraryError(
                f"a loan is due {LOAN_DAYS} days after it is borrowed, so "
                f"{self.borrowed.isoformat()} is due "
                f"{(self.borrowed + timedelta(days=LOAN_DAYS)).isoformat()}, "
                f"not {self.due.isoformat()}")
        if self.returned is not None:
            if not isinstance(self.returned, date) or \
                    isinstance(self.returned, datetime):
                raise LibraryError("a return date must be a date")
            if self.returned < self.borrowed:
                raise LibraryError(
                    f"{self.isbn} cannot be returned on "
                    f"{self.returned.isoformat()}, before it was borrowed on "
                    f"{self.borrowed.isoformat()}")

    # -- construction ------------------------------------------------------- #
    @classmethod
    def of(cls, isbn, member_id, borrowed) -> "Loan":
        """Borrow on a day; the due date is not the caller's business."""
        day = as_date(borrowed, "the borrow date")
        return cls(str(isbn), str(member_id), day,
                   day + timedelta(days=LOAN_DAYS))

    # -- state -------------------------------------------------------------- #
    @property
    def is_open(self) -> bool:
        return self.returned is None

    @property
    def key(self) -> tuple[str, str]:
        return (self.isbn, self.member_id)

    def days_late(self, day=None) -> int:
        """Days past the due date; zero on or before it."""
        if self.returned is not None:
            effective = self.returned
        else:
            if day is None:
                raise LibraryError("an open loan needs a date to judge it by")
            effective = as_date(day, "the date to judge by")
        if effective <= self.due:
            return 0
        return (effective - self.due).days

    def fine(self, day=None) -> int:
        return self.days_late(day) * FINE_PER_DAY

    def returned_on(self, day) -> "Loan":
        """A new loan with the return date filled in; the old one stands."""
        if not self.is_open:
            raise LibraryError(
                f"{self.isbn} was already returned on "
                f"{self.returned.isoformat()}")
        moment = as_date(day, "the return date")
        if moment < self.borrowed:
            raise LibraryError(
                f"{self.isbn} cannot be returned on {moment.isoformat()}, "
                f"before it was borrowed on {self.borrowed.isoformat()}")
        return Loan(self.isbn, self.member_id, self.borrowed, self.due, moment)

    # -- persistence -------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"isbn": self.isbn, "member_id": self.member_id,
                "borrowed": self.borrowed.isoformat(),
                "due": self.due.isoformat(),
                "returned": None if self.returned is None
                else self.returned.isoformat()}

    @classmethod
    def from_dict(cls, row) -> "Loan":
        if not isinstance(row, dict):
            raise LibraryError("a loan must be an object")
        unknown = set(row) - {"isbn", "member_id", "borrowed", "due",
                              "returned"}
        if unknown:
            raise LibraryError(f"unknown loan keys: {sorted(unknown)}")
        for key in ("isbn", "member_id", "borrowed", "due"):
            if key not in row:
                raise LibraryError(f"a loan is missing {key!r}")
        returned = row.get("returned")
        return cls(str(row["isbn"]).strip(), str(row["member_id"]).strip(),
                   as_date(row["borrowed"], "the borrow date"),
                   as_date(row["due"], "the due date"),
                   None if returned is None
                   else as_date(returned, "the return date"))

    def __str__(self) -> str:
        status = "out" if self.is_open else \
            f"back {self.returned.isoformat()}"
        return (f"{self.isbn:<15} {self.member_id:<6} "
                f"{self.borrowed.isoformat()}..{self.due.isoformat()}  "
                f"{status}")


# --------------------------------------------------------------------------- #
# Book: the copy count is a property, the availability is not stored
# --------------------------------------------------------------------------- #
class Book:
    """A title the library owns, and how many copies it owns."""

    def __init__(self, isbn, title, author, copies):
        self.isbn = normalise_isbn(isbn)
        if not isinstance(title, str) or not title.strip():
            raise LibraryError("a book needs a title")
        if not isinstance(author, str) or not author.strip():
            raise LibraryError("a book needs an author")
        self.title = title.strip()
        self.author = author.strip()
        self.copies = copies

    # -- the property the legacy table made a column ----------------------- #
    @property
    def copies(self) -> int:
        return self._copies

    @copies.setter
    def copies(self, value) -> None:
        self._copies = check_whole(value, "copies")

    # -- display ------------------------------------------------------------ #
    def __repr__(self) -> str:
        return (f"<Book {self.isbn} {self.title!r} by {self.author!r}, "
                f"{self.copies} copies>")

    def __str__(self) -> str:
        return (f"{self.isbn:<15} {self.title:<26.26} {self.author:<20.20} "
                f"{self.copies:>3}")

    # -- persistence -------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"isbn": self.isbn, "title": self.title,
                "author": self.author, "copies": self.copies}

    @classmethod
    def from_dict(cls, row) -> "Book":
        if not isinstance(row, dict):
            raise LibraryError("a book must be an object")
        unknown = set(row) - {"isbn", "title", "author", "copies"}
        if unknown:
            raise LibraryError(f"unknown book keys: {sorted(unknown)}")
        for key in ("isbn", "title", "author", "copies"):
            if key not in row:
                raise LibraryError(f"a book is missing {key!r}")
        return cls(row["isbn"], row["title"], row["author"], row["copies"])


# --------------------------------------------------------------------------- #
# The shared class attribute, reproduced
# --------------------------------------------------------------------------- #
def shared_shelf():
    """A class whose list lives on the class, so every instance shares it.

    This is the bug, isolated: ``a.books.append(...)`` mutates
    ``Shelf.books``, and ``b.books`` reads the same list.
    """

    class Shelf:
        books = []

    return Shelf


# --------------------------------------------------------------------------- #
# The legacy record, transcribed so the demo can prove it wrong
# --------------------------------------------------------------------------- #
def legacy_record(quantity: int) -> dict:
    """The three columns, and no rules beyond the ones the service wrote."""
    return {"quantity": quantity, "available": quantity, "issued": False}


def legacy_issue(record: dict) -> None:
    record["available"] -= 1
    if record["available"] != record["quantity"]:
        record["issued"] = True


def legacy_return(record: dict) -> None:
    record["available"] += 1
    if record["available"] == record["quantity"]:
        record["issued"] = False


def legacy_update(record: dict, quantity: int) -> None:
    """``available = max(quantity - issued, 0)`` -- the clamp that loses a copy."""
    issued = record["quantity"] - record["available"]
    record["quantity"] = quantity
    record["available"] = max(quantity - issued, 0)


# --------------------------------------------------------------------------- #
# Library: one place counts the loans, so nothing can drift
# --------------------------------------------------------------------------- #
class Library:
    """Books, members and loans, with availability computed on demand."""

    def __init__(self, name: str = "City Library"):
        if not isinstance(name, str) or not name.strip():
            raise LibraryError("the library needs a name")
        self.name = name.strip()
        self._books: dict[str, Book] = {}
        self._members: dict[str, Member] = {}
        self._loans: list[Loan] = []

    # -- construction ------------------------------------------------------- #
    @classmethod
    def empty(cls, name: str = "City Library") -> "Library":
        """A named, empty library; a class method, not a shared attribute."""
        return cls(name)

    # -- collection protocol ------------------------------------------------ #
    def __len__(self) -> int:
        """The number of titles, not the number of copies."""
        return len(self._books)

    def __iter__(self):
        return iter([self._books[isbn] for isbn in sorted(self._books)])

    def __contains__(self, isbn) -> bool:
        if not isinstance(isbn, str):
            return False
        try:
            return normalise_isbn(isbn) in self._books
        except LibraryError:
            return False

    def __repr__(self) -> str:
        return (f"<Library {self.name!r} with {len(self)} titles, "
                f"{self.total_copies} copies, {len(self.open_loans)} out>")

    @property
    def books(self) -> tuple[Book, ...]:
        return tuple(self)

    @property
    def members(self) -> tuple[Member, ...]:
        return tuple(self._members[key] for key in sorted(self._members))

    @property
    def loans(self) -> tuple[Loan, ...]:
        return tuple(self._loans)

    @property
    def open_loans(self) -> tuple[Loan, ...]:
        return tuple(loan for loan in self._loans if loan.is_open)

    @property
    def total_copies(self) -> int:
        return sum(book.copies for book in self._books.values())

    # -- books -------------------------------------------------------------- #
    def add_book(self, book: Book) -> Book:
        if not isinstance(book, Book):
            raise LibraryError("only a Book can go on the shelf")
        if book.isbn in self._books:
            raise DuplicateBook(
                f"{book.isbn} is already on the shelf as "
                f"{self._books[book.isbn].title!r}")
        self._books[book.isbn] = book
        return book

    def book(self, isbn) -> Book:
        key = normalise_isbn(isbn)
        try:
            return self._books[key]
        except KeyError:
            raise LibraryError(f"no book with ISBN {key}") from None

    def remove_book(self, isbn) -> Book:
        book = self.book(isbn)
        out = [loan for loan in self.open_loans if loan.isbn == book.isbn]
        if out:
            raise LibraryError(
                f"{book.isbn} has {len(out)} copy or copies on loan, "
                f"starting with {out[0].member_id}")
        del self._books[book.isbn]
        return book

    def set_copies(self, isbn, copies) -> Book:
        """Change how many copies the library owns, refusing to lose a loan."""
        book = self.book(isbn)
        wanted = check_whole(copies, "copies")
        out = self.on_loan(book.isbn)
        if wanted < out:
            raise LibraryError(
                f"{book.isbn} owns {book.copies} copies and {out} are on "
                f"loan; it cannot own only {wanted}")
        book.copies = wanted
        return book

    def search(self, text: str) -> list[Book]:
        if not isinstance(text, str):
            raise LibraryError("a search needs text")
        needle = text.strip().casefold()
        if not needle:
            raise LibraryError("a search needs something to look for")
        return [book for book in self.books
                if needle in book.isbn.casefold()
                or needle in book.title.casefold()
                or needle in book.author.casefold()]

    # -- members ------------------------------------------------------------ #
    def add_member(self, member: Member) -> Member:
        if not isinstance(member, Member):
            raise LibraryError("only a Member can be registered")
        key = member.member_id.strip()
        if key in self._members:
            raise DuplicateMember(
                f"{key} is already registered as "
                f"{self._members[key].name!r}")
        self._members[key] = Member(key, member.name.strip(), member.limit)
        return self._members[key]

    def member(self, member_id) -> Member:
        if not isinstance(member_id, str):
            raise LibraryError("a member id must be text")
        key = member_id.strip()
        try:
            return self._members[key]
        except KeyError:
            raise LibraryError(f"no member with id {key}") from None

    def open_loans_of(self, member_id) -> tuple[Loan, ...]:
        key = self.member(member_id).member_id
        return tuple(loan for loan in self._loans
                     if loan.is_open and loan.member_id == key)

    # -- derived counts ----------------------------------------------------- #
    def on_loan(self, isbn) -> int:
        """Open loans of one ISBN; the only number the shelf does not hold."""
        key = self.book(isbn).isbn
        return sum(1 for loan in self._loans
                   if loan.is_open and loan.isbn == key)

    def available(self, isbn) -> int:
        book = self.book(isbn)
        return book.copies - self.on_loan(book.isbn)

    def issued(self, isbn) -> bool:
        """The legacy column, now a question: is any copy out?"""
        return self.on_loan(isbn) > 0

    # -- lending ------------------------------------------------------------ #
    def borrow(self, isbn, member_id, day) -> Loan:
        book = self.book(isbn)
        member = self.member(member_id)
        moment = as_date(day, "the borrow date")
        if self.available(book.isbn) < 1:
            raise NoCopiesLeft(f"every copy of {book.isbn} is already out")
        held = self.open_loans_of(member.member_id)
        if any(loan.isbn == book.isbn for loan in held):
            raise LibraryError(
                f"{member.member_id} already has {book.isbn} on loan")
        if len(held) >= member.limit:
            raise LoanLimitReached(
                f"{member.member_id} already holds {len(held)} of "
                f"{member.limit} allowed")
        loan = Loan.of(book.isbn, member.member_id, moment)
        self._loans.append(loan)
        return loan

    def give_back(self, isbn, member_id, day) -> tuple[Loan, int]:
        """Close a loan and return it with the fine that was owed."""
        book = self.book(isbn)
        member = self.member(member_id)
        moment = as_date(day, "the return date")
        for index, loan in enumerate(self._loans):
            if loan.is_open and loan.isbn == book.isbn and \
                    loan.member_id == member.member_id:
                closed = loan.returned_on(moment)
                self._loans[index] = closed
                return closed, closed.fine()
        raise LibraryError(
            f"{member.member_id} has no open loan of {book.isbn}")

    # -- reports ------------------------------------------------------------ #
    def overdue(self, day) -> list[Loan]:
        moment = as_date(day, "the date to judge by")
        late = [loan for loan in self._loans
                if loan.is_open and loan.days_late(moment) > 0]
        return sorted(late, key=lambda loan: (loan.due, loan.isbn))

    def fines(self, day) -> dict[str, int]:
        moment = as_date(day, "the date to judge by")
        totals: dict[str, int] = {}
        for loan in self.overdue(moment):
            totals[loan.member_id] = \
                totals.get(loan.member_id, 0) + loan.fine(moment)
        return dict(sorted(totals.items()))

    def total_fine(self, day) -> int:
        return sum(self.fines(day).values())

    # -- invariants --------------------------------------------------------- #
    def consistency(self) -> list[tuple[str, bool]]:
        """Five invariants, each reported by name and verdict."""
        checks = []

        negative = [book.isbn for book in self._books.values()
                    if not isinstance(book.copies, int)
                    or isinstance(book.copies, bool)
                    or book.copies < 0]
        checks.append(("no book has negative copies", not negative))

        over = [book.isbn for book in self._books.values()
                if self.on_loan(book.isbn) > book.copies]
        checks.append(("no book has more copies out than it owns", not over))

        known = all(loan.isbn in self._books
                    and loan.member_id in self._members
                    for loan in self.open_loans)
        checks.append(("every open loan names a book and a member on record",
                       known))

        dated = all(isinstance(loan.due, date)
                    and loan.due == loan.borrowed + timedelta(days=LOAN_DAYS)
                    for loan in self._loans)
        checks.append((f"every loan is due {LOAN_DAYS} days after it was "
                       f"borrowed", dated))

        limits = all(len(self.open_loans_of(member.member_id)) <= member.limit
                     for member in self._members.values())
        checks.append(("no member is over their limit", limits))
        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.consistency() if not passed]

    # -- persistence -------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"name": self.name,
                "books": [book.to_dict() for book in self],
                "members": [member.to_dict() for member in self.members],
                "loans": [loan.to_dict() for loan in self._loans]}

    @classmethod
    def from_dict(cls, payload) -> "Library":
        if not isinstance(payload, dict):
            raise LibraryError("a library document must be an object")
        unknown = set(payload) - {"name", "books", "members", "loans"}
        if unknown:
            raise LibraryError(f"unknown library keys: {sorted(unknown)}")
        for key in ("name", "books", "members", "loans"):
            if key not in payload:
                raise LibraryError(f"the library is missing {key!r}")
        for key in ("books", "members", "loans"):
            if not isinstance(payload[key], list):
                raise LibraryError(f"{key!r} must be a list")
        library = cls(payload["name"])
        for row in payload["books"]:
            library.add_book(Book.from_dict(row))
        for row in payload["members"]:
            library.add_member(Member.from_dict(row))
        for row in payload["loans"]:
            loan = Loan.from_dict(row)
            library.book(loan.isbn)
            library.member(loan.member_id)
            library._loans.append(loan)
        return library


def load_library(path=DATA_FILE) -> Library:
    path = Path(path)
    if not path.exists():
        raise LibraryError(f"library file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LibraryError(f"{path.name} is not valid JSON: {exc}") from None
    return Library.from_dict(payload)


def save_library(path, library: Library) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(library.to_dict(), indent=2) + "\n",
                    encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 74)
    print(" LIBRARY - a stored flag that drifts, and a count that cannot")
    print("=" * 74)

    # 1. the legacy ISBN test took any five characters
    assert legacy_isbn_ok("abcde")
    assert not isbn_is_valid("abcde")
    refused = 0
    for bad in ("abcde", "12345", "9780132350885", "030640615X", "",
                "978-0-13-235088-4-1"):
        try:
            normalise_isbn(bad)
        except LibraryError:
            refused += 1
        else:
            raise AssertionError(f"{bad!r} was accepted as an ISBN")
    assert refused == 6
    tidy = normalise_isbn("978-0-13-235 088-4")
    assert tidy == "9780132350884" and isbn_kind("0-306-40615-2") == 10
    print(f"  legacy len(text) >= 5 accepted 'abcde'; the checksum refused "
          f"{refused} bad ISBNs and tidied '978-0-13-235 088-4' to {tidy}")

    # 2. the stored flag, and the clamp that loses a copy
    record = legacy_record(5)
    for _ in range(4):
        legacy_issue(record)
    assert (record["available"], record["issued"]) == (1, True)
    legacy_update(record, 3)
    assert (record["quantity"], record["available"]) == (3, 0)
    legacy_return(record)
    legacy_return(record)
    assert (record["quantity"], record["available"]) == (3, 2)
    open_loans = 4 - 2
    assert record["quantity"] - record["available"] == 1
    assert open_loans == 2
    print(f"  legacy: 4 of 5 out, then quantity:=3 -> available "
          f"max(3-4,0)=0; after 2 returns the record implies 1 out while "
          f"{open_loans} loans are still open")

    # 3. the class attribute everyone shares
    Shelf = shared_shelf()
    first, second = Shelf(), Shelf()
    first.books.append("Dune")
    assert second.books == ["Dune"] and first.books is second.books
    assert Shelf.books is first.books
    one, two = Library.empty("North"), Library.empty("South")
    one.add_book(Book("9780306406157", "Dune", "Frank Herbert", 1))
    assert len(one) == 1 and len(two) == 0
    assert one._books is not two._books
    print(f"  legacy class attribute: appending on one instance gave "
          f"{second.books}; two Library instances keep {len(one)} and "
          f"{len(two)} titles")

    # 4. copies is a property, availability is derived
    book = Book("9780132350884", "Clean Code", "Robert C. Martin", 3)
    refused = 0
    for bad in (-1, 1.5, True, "3"):
        try:
            book.copies = bad
        except LibraryError:
            refused += 1
        else:
            raise AssertionError(f"{bad!r} was accepted as a copy count")
    assert refused == 4 and book.copies == 3
    book.copies = 4
    assert book.copies == 4
    house = Library.empty("Demo")
    house.add_book(book)
    house.add_member(Member("M-01", "Asha Rao"))
    assert house.available(book.isbn) == 4 and not house.issued(book.isbn)
    house.borrow(book.isbn, "M-01", "2026-03-02")
    assert house.available(book.isbn) == 3 and house.issued(book.isbn)
    print(f"  Book.copies refused {refused} bad values; 4 copies -> 1 loan "
          f"gives available 3 and issued True, with no flag to update")

    # 5. loans have a due date, and the fine starts the day after
    house.add_member(Member("M-02", "Bilal Khan", 2))
    loan = house.borrow(book.isbn, "M-02", "2026-03-02")
    assert loan.due.isoformat() == "2026-03-16"
    assert loan.days_late("2026-03-16") == 0 and loan.fine("2026-03-16") == 0
    assert loan.days_late("2026-03-17") == 1 and loan.fine("2026-03-17") == 25
    assert loan.days_late("2026-03-20") == 4 and loan.fine("2026-03-20") == 100
    assert money(100) == "Rs 1.00"
    print(f"  borrowed 2026-03-02, due {loan.due.isoformat()}: 0 days late on "
          f"the due date, 1 day late the next day (25 cents), 4 days = "
          f"{money(100)}")

    # 6. the limit, the duplicate, and the shrink that is refused
    house.add_member(Member("M-03", "Chen Wei", 2))
    house.add_book(Book("9780201633610", "Design Patterns", "Erich Gamma", 2))
    house.add_book(Book("0306406152", "The Art of Computer Programming",
                        "Donald Knuth", 1))
    house.borrow(book.isbn, "M-03", "2026-03-03")
    house.borrow("9780201633610", "M-03", "2026-03-03")
    try:
        house.borrow("0306406152", "M-03", "2026-03-04")
    except LoanLimitReached as exc:
        limit_message = str(exc)
    else:
        raise AssertionError("a member borrowed past their limit")
    assert "2 of 2 allowed" in limit_message
    try:
        house.borrow(book.isbn, "M-03", "2026-03-04")
    except LibraryError as exc:
        duplicate = str(exc)
    else:
        raise AssertionError("the same book was borrowed twice")
    assert "already has" in duplicate
    receipt, fine = house.give_back(book.isbn, "M-03", "2026-03-20")
    assert fine == 75 and not receipt.is_open
    assert not house.problems()
    try:
        house.set_copies(book.isbn, 1)
    except LibraryError as exc:
        shrink = str(exc)
    else:
        raise AssertionError("copies were cut below the loans")
    assert "2 are on loan" in shrink
    print(f"  M-03 (limit 2) was refused a third book ({limit_message}); the "
          f"same ISBN twice was refused too")
    print(f"  one return cost {fine} cents; set_copies(1) was refused while "
          f"2 copies are out")

    # 7. every copy out is refused, not silently oversold
    thin = Library.empty("Thin")
    thin.add_book(Book("9780596517748", "The Good Parts", "Douglas Crockford",
                       1))
    thin.add_member(Member("M-01", "Asha Rao"))
    thin.borrow("9780596517748", "M-01", "2026-03-01")
    assert thin.available("9780596517748") == 0 and \
        thin.issued("9780596517748")
    try:
        thin.borrow("9780596517748", "M-01", "2026-03-02")
    except NoCopiesLeft as exc:
        empty_message = str(exc)
    else:
        raise AssertionError("a copy that does not exist was lent")
    print(f"  one copy, one loan: the second borrow refused "
          f"({empty_message[:40]}...)")

    # 8. the seeded library
    seeded = load_library()
    day = "2026-03-10"
    assert len(seeded) == 6 and seeded.total_copies == 10
    assert len(seeded.members) == 3
    assert len(seeded.open_loans) == 4 and len(seeded.loans) == 5
    assert seeded.problems() == []
    assert seeded.available("9780132350884") == 2
    assert seeded.available("9780596517748") == 0
    assert seeded.issued("9780596517748")
    late = seeded.overdue(day)
    assert len(late) == 1 and late[0].days_late(day) == 4
    assert seeded.fines(day) == {"M-02": 100}
    assert seeded.total_fine(day) == 100
    print(f"  seeded: 6 titles, 10 copies, 3 members, 4 of 5 loans out; on "
          f"{day} one loan is 4 days late and the fine is "
          f"{seeded.total_fine(day)} cents")

    # 9. a hand-added loan breaks exactly one invariant
    broken = Library.from_dict(seeded.to_dict())
    for day_text in ("2026-03-11", "2026-03-12"):
        broken._loans.append(Loan.of("9780306406157", "M-02", day_text))
    assert broken.consistency() == broken.consistency()
    assert broken.problems() == ["no member is over their limit"]
    print(f"  M-02's limit is 2 and 3 loans were forced on: exactly 1 of 5 "
          f"checks fails")

    # 10. save and load
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "copy.json"
        save_library(target, seeded)
        first_bytes = target.read_bytes()
        save_library(target, load_library(target))
        assert target.read_bytes() == first_bytes
        assert load_library(target).to_dict() == seeded.to_dict()
    print("  the seeded library saves and reloads byte for byte")

    print()
    print("Cross-checks OK: the legacy len(text) >= 5 test accepted 'abcde' "
          "while the real checksum refused 6 bad ISBNs and normalised a "
          "spaced one, the legacy stored flag and its max(..., 0) clamp left "
          "1 copy implied on loan against 2 real loans, a class attribute "
          "leaked one instance's books into another while two Library "
          "instances stayed separate, Book.copies refused 4 bad values and "
          "availability followed the loans, a loan due on the 16th was free "
          "that day and 25 cents late the next, a member's limit and an "
          "empty shelf were both refused with the numbers named, a shrink "
          "below the loans was refused, the seeded 6 titles and 10 copies "
          "had 4 open loans with 4 days late and a 100 cent fine on "
          "2026-03-10, one forced loan failed exactly one of 5 checks, and "
          "the file round-tripped byte for byte")
    print("\nDemo completed successfully.")
    return 0
