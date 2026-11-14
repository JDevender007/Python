"""Tests for Library_Management_System: ISBNs, loans, books, the library."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from library import (                                     # noqa: E402
    DATA_FILE,
    FINE_PER_DAY,
    LEGACY_ISBN,
    LEGACY_ISSUED,
    LEGACY_SHARED,
    LOAN_DAYS,
    Book,
    DuplicateBook,
    DuplicateMember,
    Library,
    LibraryError,
    Loan,
    LoanLimitReached,
    Member,
    NoCopiesLeft,
    as_date,
    check_whole,
    isbn_is_valid,
    isbn_kind,
    legacy_isbn_ok,
    legacy_issue,
    legacy_record,
    legacy_return,
    legacy_update,
    load_library,
    money,
    normalise_isbn,
    run_demo,
    save_library,
    shared_shelf,
)

CLEAN = "9780132350884"
GOOD_PARTS = "9780596517748"
PRAGMATIC = "9780306406157"
KNUTH = "0306406152"
REFACTORING = "9781402894626"
DAY = "2026-03-10"


def a_book(isbn=CLEAN, copies=3, title="Clean Code",
           author="Robert C. Martin"):
    return Book(isbn, title, author, copies)


def a_library(*specs) -> Library:
    """A library with CLEAN (3 copies), GOOD_PARTS (1) and a member."""
    library = Library("Test Library")
    for isbn, copies in specs or ((CLEAN, 3), (GOOD_PARTS, 1)):
        library.add_book(Book(isbn, f"Book {isbn[-3:]}", "An Author", copies))
    library.add_member(Member("M-01", "Asha Rao"))
    return library


# --------------------------------------------------------------------------- #
# as_date
# --------------------------------------------------------------------------- #
def test_as_date_accepts_iso_text():
    assert as_date("2026-03-02") == date(2026, 3, 2)


def test_as_date_accepts_a_date_object():
    assert as_date(date(2026, 3, 2)) == date(2026, 3, 2)


def test_as_date_trims_the_text():
    assert as_date("  2026-03-02 ") == date(2026, 3, 2)


@pytest.mark.parametrize("bad", ["2026-3-2", "2026-03-2", "2026/03/02",
                                 "02-03-2026", "2026-03", "20260302", ""])
def test_as_date_refuses_a_non_canonical_shape(bad):
    with pytest.raises(LibraryError):
        as_date(bad)


def test_as_date_refuses_the_30th_of_february():
    with pytest.raises(LibraryError, match="not a real date"):
        as_date("2026-02-30")


def test_as_date_refuses_the_basic_iso_format():
    with pytest.raises(LibraryError, match="not a canonical date"):
        as_date("20260302")


def test_as_date_refuses_an_integer():
    with pytest.raises(LibraryError, match="got int"):
        as_date(20260302)


def test_as_date_refuses_a_boolean():
    with pytest.raises(LibraryError, match="got bool"):
        as_date(True)


def test_as_date_refuses_a_datetime():
    with pytest.raises(LibraryError, match="not a datetime"):
        as_date(datetime(2026, 3, 2, 9, 0))


def test_as_date_uses_its_label():
    with pytest.raises(LibraryError, match="the due date must be a date"):
        as_date(7, "the due date")


# --------------------------------------------------------------------------- #
# check_whole / money
# --------------------------------------------------------------------------- #
def test_check_whole_returns_the_number():
    assert check_whole(4) == 4


def test_check_whole_allows_zero():
    assert check_whole(0) == 0


def test_check_whole_refuses_a_negative():
    with pytest.raises(LibraryError, match="must not be negative"):
        check_whole(-1)


def test_check_whole_refuses_a_float():
    with pytest.raises(LibraryError, match="whole number"):
        check_whole(1.0)


def test_check_whole_refuses_a_bool():
    with pytest.raises(LibraryError, match="got bool"):
        check_whole(True)


def test_check_whole_uses_its_label():
    with pytest.raises(LibraryError, match="copies must not be negative"):
        check_whole(-1, "copies")


def test_money_pins_a_fine():
    assert money(25) == "Rs 0.25"


def test_money_renders_a_whole_rupee():
    assert money(100) == "Rs 1.00"


def test_money_renders_zero():
    assert money(0) == "Rs 0.00"


def test_money_groups_thousands():
    assert money(123456) == "Rs 1,234.56"


def test_money_renders_a_negative_amount():
    assert money(-25) == "-Rs 0.25"


def test_money_refuses_a_float():
    with pytest.raises(LibraryError, match="integer number of cents"):
        money(1.5)


# --------------------------------------------------------------------------- #
# ISBNs
# --------------------------------------------------------------------------- #
def test_a_valid_isbn_13_is_accepted():
    assert normalise_isbn(CLEAN) == CLEAN


def test_a_hyphenated_isbn_is_normalised():
    assert normalise_isbn("978-0-13-235088-4") == CLEAN


def test_a_spaced_and_hyphenated_isbn_is_normalised():
    assert normalise_isbn("978-0-13-235 088-4") == CLEAN


def test_a_valid_isbn_10_is_accepted():
    assert normalise_isbn("0-306-40615-2") == KNUTH


def test_an_isbn_10_with_an_x_check_digit_is_accepted():
    assert normalise_isbn("080442957x") == "080442957X"


def test_an_isbn_that_is_not_text_is_refused():
    with pytest.raises(LibraryError, match="must be text"):
        normalise_isbn(9780132350884)


def test_an_empty_isbn_is_refused():
    with pytest.raises(LibraryError, match="must not be empty"):
        normalise_isbn("   ")


@pytest.mark.parametrize("bad", ["abcde", "12345", "9780132350885",
                                 "030640615X", "978013235088", "97801323508841",
                                 "97801323508X4"])
def test_a_bad_checksum_is_refused(bad):
    with pytest.raises(LibraryError, match="not a valid ISBN"):
        normalise_isbn(bad)


def test_isbn_is_valid_is_false_for_a_non_string():
    assert isbn_is_valid(9780132350884) is False


def test_isbn_is_valid_is_false_for_a_bad_check_digit():
    assert isbn_is_valid("9780132350885") is False


def test_isbn_is_valid_accepts_hyphens():
    assert isbn_is_valid("978-0-13-235088-4") is True


def test_isbn_kind_reports_ten():
    assert isbn_kind("0-306-40615-2") == 10


def test_isbn_kind_reports_thirteen():
    assert isbn_kind(CLEAN) == 13


def test_the_legacy_test_accepted_any_five_characters():
    assert legacy_isbn_ok("abcde") is True


def test_the_legacy_test_refused_four_characters():
    assert legacy_isbn_ok("abcd") is False


def test_the_legacy_test_passed_a_real_isbn():
    assert legacy_isbn_ok(CLEAN) is True


# --------------------------------------------------------------------------- #
# Member
# --------------------------------------------------------------------------- #
def test_a_member_keeps_its_id():
    assert Member("M-01", "Asha Rao").member_id == "M-01"


def test_a_member_defaults_to_three_books():
    assert Member("M-01", "Asha Rao").limit == 3


def test_a_member_takes_a_limit():
    assert Member("M-01", "Asha Rao", 2).limit == 2


def test_a_member_needs_an_id():
    with pytest.raises(LibraryError, match="needs an id"):
        Member("  ", "Asha Rao")


def test_a_member_needs_a_name():
    with pytest.raises(LibraryError, match="needs a name"):
        Member("M-01", "   ")


def test_a_member_refuses_a_float_limit():
    with pytest.raises(LibraryError, match="whole number"):
        Member("M-01", "Asha Rao", 2.0)


def test_a_member_refuses_a_bool_limit():
    with pytest.raises(LibraryError, match="whole number"):
        Member("M-01", "Asha Rao", True)


def test_a_member_refuses_a_zero_limit():
    with pytest.raises(LibraryError, match="at least one"):
        Member("M-01", "Asha Rao", 0)


def test_a_member_is_frozen():
    with pytest.raises(Exception):
        Member("M-01", "Asha").name = "B"                # type: ignore[misc]


def test_a_member_dict_is_trimmed():
    assert Member("  M-01 ", "  Asha Rao  ", 2).to_dict() == {
        "member_id": "M-01", "name": "Asha Rao", "limit": 2}


def test_a_member_round_trips():
    member = Member("M-01", "Asha Rao", 2)
    assert Member.from_dict(member.to_dict()) == member


def test_member_from_dict_defaults_the_limit():
    assert Member.from_dict({"member_id": "M-01", "name": "A"}).limit == 3


def test_member_from_dict_refuses_a_non_object():
    with pytest.raises(LibraryError, match="must be an object"):
        Member.from_dict([])


def test_member_from_dict_refuses_an_unknown_key():
    with pytest.raises(LibraryError, match="unknown member keys"):
        Member.from_dict({"member_id": "M-01", "name": "A", "phone": "1"})


def test_member_from_dict_requires_a_name():
    with pytest.raises(LibraryError, match="missing 'name'"):
        Member.from_dict({"member_id": "M-01"})


# --------------------------------------------------------------------------- #
# Loan
# --------------------------------------------------------------------------- #
def test_the_loan_window_is_fourteen_days():
    assert LOAN_DAYS == 14


def test_a_loan_is_due_two_weeks_after_the_borrow_date():
    loan = Loan.of(CLEAN, "M-01", "2026-03-02")
    assert loan.due == date(2026, 3, 16)


def test_loan_of_accepts_a_date_object():
    assert Loan.of(CLEAN, "M-01", date(2026, 3, 2)).borrowed == \
        date(2026, 3, 2)


def test_a_new_loan_is_open():
    assert Loan.of(CLEAN, "M-01", DAY).is_open


def test_a_loan_key_is_the_isbn_and_member():
    assert Loan.of(CLEAN, "M-01", DAY).key == (CLEAN, "M-01")


def test_a_loan_needs_an_isbn():
    with pytest.raises(LibraryError, match="needs an ISBN"):
        Loan("  ", "M-01", date(2026, 3, 2), date(2026, 3, 16))


def test_a_loan_needs_a_member():
    with pytest.raises(LibraryError, match="needs a member id"):
        Loan(CLEAN, "  ", date(2026, 3, 2), date(2026, 3, 16))


def test_a_loan_needs_a_borrow_date():
    with pytest.raises(LibraryError, match="needs a borrow date"):
        Loan(CLEAN, "M-01", "2026-03-02", date(2026, 3, 16))


def test_a_loan_needs_a_due_date():
    with pytest.raises(LibraryError, match="needs a due date"):
        Loan(CLEAN, "M-01", date(2026, 3, 2), "2026-03-16")


def test_a_loan_refuses_a_wrong_due_date():
    with pytest.raises(LibraryError, match="is due 14 days"):
        Loan(CLEAN, "M-01", date(2026, 3, 2), date(2026, 3, 15))


def test_a_loan_names_the_due_date_it_wanted():
    with pytest.raises(LibraryError, match="is due 2026-03-16"):
        Loan(CLEAN, "M-01", date(2026, 3, 2), date(2026, 3, 20))


def test_a_loan_refuses_a_return_before_the_borrow():
    with pytest.raises(LibraryError, match="before it was borrowed"):
        Loan(CLEAN, "M-01", date(2026, 3, 2), date(2026, 3, 16),
             date(2026, 3, 1))


def test_a_loan_refuses_a_string_return_date():
    with pytest.raises(LibraryError, match="a return date must be a date"):
        Loan(CLEAN, "M-01", date(2026, 3, 2), date(2026, 3, 16), "2026-03-03")


def test_days_late_is_zero_on_the_due_date():
    assert Loan.of(CLEAN, "M-01", "2026-03-02").days_late("2026-03-16") == 0


def test_days_late_is_zero_before_the_due_date():
    assert Loan.of(CLEAN, "M-01", "2026-03-02").days_late("2026-03-10") == 0


def test_days_late_is_one_the_day_after():
    assert Loan.of(CLEAN, "M-01", "2026-03-02").days_late("2026-03-17") == 1


def test_days_late_is_four_four_days_after():
    assert Loan.of(CLEAN, "M-01", "2026-03-02").days_late(DAY) == 0


def test_the_fine_is_per_day():
    assert FINE_PER_DAY == 25


def test_a_late_loan_owes_a_fine():
    assert Loan.of(CLEAN, "M-01", "2026-03-02").fine("2026-03-20") == 100


def test_an_on_time_loan_owes_nothing():
    assert Loan.of(CLEAN, "M-01", "2026-03-02").fine("2026-03-16") == 0


def test_an_open_loan_needs_a_date_to_judge_it_by():
    with pytest.raises(LibraryError, match="needs a date to judge it by"):
        Loan.of(CLEAN, "M-01", DAY).days_late()


def test_a_returned_loan_judges_itself_from_the_return_date():
    loan = Loan.of(CLEAN, "M-01", "2026-03-02").returned_on("2026-03-20")
    assert loan.days_late() == 4 and loan.fine() == 100


def test_a_returned_loan_on_time_owes_nothing():
    loan = Loan.of(CLEAN, "M-01", "2026-03-02").returned_on("2026-03-10")
    assert loan.fine() == 0


def test_returning_a_loan_produces_a_new_value():
    loan = Loan.of(CLEAN, "M-01", "2026-03-02")
    back = loan.returned_on("2026-03-10")
    assert loan.is_open and not back.is_open
    assert back.returned == date(2026, 3, 10)


def test_a_loan_cannot_be_returned_twice():
    back = Loan.of(CLEAN, "M-01", "2026-03-02").returned_on("2026-03-10")
    with pytest.raises(LibraryError, match="already returned"):
        back.returned_on("2026-03-11")


def test_a_loan_cannot_be_returned_before_it_was_borrowed():
    with pytest.raises(LibraryError, match="before it was borrowed"):
        Loan.of(CLEAN, "M-01", "2026-03-02").returned_on("2026-03-01")


def test_a_loan_round_trips():
    loan = Loan.of(CLEAN, "M-01", "2026-03-02")
    assert Loan.from_dict(loan.to_dict()) == loan


def test_a_returned_loan_round_trips():
    loan = Loan.of(CLEAN, "M-01", "2026-03-02").returned_on("2026-03-20")
    assert Loan.from_dict(loan.to_dict()) == loan


def test_loan_from_dict_allows_a_missing_return_date():
    payload = {"isbn": CLEAN, "member_id": "M-01",
               "borrowed": "2026-03-02", "due": "2026-03-16"}
    assert Loan.from_dict(payload).is_open


def test_loan_from_dict_refuses_a_non_object():
    with pytest.raises(LibraryError, match="must be an object"):
        Loan.from_dict("2026-03-02")


def test_loan_from_dict_refuses_an_unknown_key():
    row = Loan.of(CLEAN, "M-01", "2026-03-02").to_dict()
    row["note"] = "x"
    with pytest.raises(LibraryError, match="unknown loan keys"):
        Loan.from_dict(row)


def test_loan_from_dict_requires_the_due_date():
    row = Loan.of(CLEAN, "M-01", "2026-03-02").to_dict()
    del row["due"]
    with pytest.raises(LibraryError, match="missing 'due'"):
        Loan.from_dict(row)


def test_loan_from_dict_refuses_a_wrong_due_date():
    row = Loan.of(CLEAN, "M-01", "2026-03-02").to_dict()
    row["due"] = "2026-03-30"
    with pytest.raises(LibraryError, match="is due 14 days"):
        Loan.from_dict(row)


def test_an_open_loan_str_says_out():
    assert str(Loan.of(CLEAN, "M-01", "2026-03-02")).endswith("out")


def test_a_returned_loan_str_names_the_day():
    back = Loan.of(CLEAN, "M-01", "2026-03-02").returned_on("2026-03-20")
    assert "back 2026-03-20" in str(back)


def test_a_loan_is_frozen():
    with pytest.raises(Exception):
        Loan.of(CLEAN, "M-01", DAY).due = date(2026, 1, 1)  # type: ignore


# --------------------------------------------------------------------------- #
# Book
# --------------------------------------------------------------------------- #
def test_a_book_normalises_its_isbn():
    assert a_book("978-0-13-235088-4").isbn == CLEAN


def test_a_book_trims_its_title():
    assert Book(CLEAN, "  Clean Code  ", "A", 1).title == "Clean Code"


def test_a_book_trims_its_author():
    assert Book(CLEAN, "T", "  Robert C. Martin ", 1).author == \
        "Robert C. Martin"


def test_a_book_keeps_its_copy_count():
    assert a_book(copies=4).copies == 4


def test_a_book_needs_a_title():
    with pytest.raises(LibraryError, match="needs a title"):
        Book(CLEAN, "   ", "A", 1)


def test_a_book_needs_an_author():
    with pytest.raises(LibraryError, match="needs an author"):
        Book(CLEAN, "T", "  ", 1)


def test_a_book_needs_a_valid_isbn():
    with pytest.raises(LibraryError, match="not a valid ISBN"):
        Book("abcde", "T", "A", 1)


def test_a_book_refuses_a_negative_copy_count():
    with pytest.raises(LibraryError, match="must not be negative"):
        Book(CLEAN, "T", "A", -1)


def test_a_book_refuses_a_float_copy_count():
    with pytest.raises(LibraryError, match="whole number"):
        Book(CLEAN, "T", "A", 1.0)


def test_a_book_refuses_a_bool_copy_count():
    with pytest.raises(LibraryError, match="whole number"):
        Book(CLEAN, "T", "A", True)


def test_a_book_allows_zero_copies():
    assert Book(CLEAN, "T", "A", 0).copies == 0


def test_the_copies_setter_accepts_a_count():
    book = a_book(copies=3)
    book.copies = 5
    assert book.copies == 5


def test_the_copies_setter_refuses_a_negative():
    book = a_book(copies=3)
    with pytest.raises(LibraryError, match="must not be negative"):
        book.copies = -1
    assert book.copies == 3


def test_the_copies_setter_refuses_a_float():
    book = a_book(copies=3)
    with pytest.raises(LibraryError, match="whole number"):
        book.copies = 2.0
    assert book.copies == 3


def test_a_book_repr_names_the_copies():
    text = repr(a_book(copies=3))
    assert CLEAN in text and "Clean Code" in text and "3 copies" in text


def test_a_book_str_is_one_row():
    assert str(a_book(copies=3)).startswith(CLEAN)


def test_a_book_round_trips():
    book = a_book(copies=3)
    assert Book.from_dict(book.to_dict()).to_dict() == book.to_dict()


def test_book_from_dict_refuses_a_non_object():
    with pytest.raises(LibraryError, match="must be an object"):
        Book.from_dict([])


def test_book_from_dict_refuses_an_unknown_key():
    row = a_book().to_dict()
    row["shelf"] = "A1"
    with pytest.raises(LibraryError, match="unknown book keys"):
        Book.from_dict(row)


def test_book_from_dict_requires_the_copies():
    row = a_book().to_dict()
    del row["copies"]
    with pytest.raises(LibraryError, match="missing 'copies'"):
        Book.from_dict(row)


# --------------------------------------------------------------------------- #
# The shared class attribute
# --------------------------------------------------------------------------- #
def test_the_legacy_constant_is_the_anti_pattern():
    assert LEGACY_SHARED == "books = []"


def test_two_shelves_share_one_list():
    Shelf = shared_shelf()
    first, second = Shelf(), Shelf()
    first.books.append("Dune")
    assert second.books == ["Dune"]


def test_the_shared_list_is_the_class_attribute():
    Shelf = shared_shelf()
    first = Shelf()
    assert first.books is Shelf.books


def test_a_fresh_factory_gives_a_fresh_list():
    first = shared_shelf()
    second = shared_shelf()
    first().books.append("Dune")
    assert second().books == []


# --------------------------------------------------------------------------- #
# The legacy record
# --------------------------------------------------------------------------- #
def test_a_legacy_record_starts_available():
    assert legacy_record(5) == {"quantity": 5, "available": 5,
                                "issued": False}


def test_a_legacy_issue_flags_the_record():
    record = legacy_record(2)
    legacy_issue(record)
    assert record["available"] == 1 and record["issued"] is True


def test_a_legacy_return_clears_the_flag():
    record = legacy_record(1)
    legacy_issue(record)
    legacy_return(record)
    assert record["available"] == 1 and record["issued"] is False


def test_a_legacy_issue_has_no_lower_bound():
    record = legacy_record(1)
    legacy_issue(record)
    legacy_issue(record)
    assert record["available"] == -1


def test_a_legacy_update_clamps_away_the_extra_loan():
    record = legacy_record(5)
    for _ in range(4):
        legacy_issue(record)
    legacy_update(record, 3)
    assert record["quantity"] == 3 and record["available"] == 0


def test_the_legacy_record_drifts_by_one_copy():
    record = legacy_record(5)
    for _ in range(4):
        legacy_issue(record)
    legacy_update(record, 3)
    legacy_return(record)
    legacy_return(record)
    assert record["quantity"] - record["available"] == 1
    assert 4 - 2 == 2                       # two loans are still open


def test_the_legacy_constant_is_the_stored_flag():
    assert LEGACY_ISSUED == "issued = Column(Boolean, default=False)"


def test_the_legacy_isbn_constant_is_the_five_character_test():
    assert LEGACY_ISBN == "return len(value.strip()) >= 5"


# --------------------------------------------------------------------------- #
# Library: construction and the collection protocol
# --------------------------------------------------------------------------- #
def test_a_library_needs_a_name():
    with pytest.raises(LibraryError, match="needs a name"):
        Library("  ")


def test_a_library_needs_a_text_name():
    with pytest.raises(LibraryError, match="needs a name"):
        Library(7)


def test_a_library_trims_its_name():
    assert Library("  North  ").name == "North"


def test_a_library_defaults_its_name():
    assert Library().name == "City Library"


def test_empty_is_a_class_method():
    assert isinstance(Library.empty("North"), Library)


def test_empty_gives_each_instance_its_own_shelves():
    first, second = Library.empty("North"), Library.empty("South")
    first.add_book(a_book())
    assert len(first) == 1 and len(second) == 0
    assert first._books is not second._books


def test_len_counts_the_titles():
    assert len(a_library()) == 2


def test_total_copies_counts_every_copy():
    assert a_library().total_copies == 4


def test_iteration_is_in_isbn_order():
    library = a_library((GOOD_PARTS, 1), (CLEAN, 3))
    assert [book.isbn for book in library] == [CLEAN, GOOD_PARTS]


def test_books_is_a_tuple():
    assert isinstance(a_library().books, tuple)


def test_contains_accepts_an_isbn():
    assert CLEAN in a_library()


def test_contains_normalises_hyphens():
    assert "978-0-13-235088-4" in a_library()


def test_contains_is_false_for_an_unknown_isbn():
    assert REFACTORING not in a_library()


def test_contains_is_false_for_an_invalid_isbn():
    assert "abcde" not in a_library()


def test_contains_is_false_for_a_non_string():
    assert 9780132350884 not in a_library()


def test_a_library_repr_reports_its_counts():
    text = repr(a_library())
    assert "Test Library" in text and "2 titles" in text and "4 copies" in text


def test_members_are_sorted_by_id():
    library = a_library()
    library.add_member(Member("M-00", "First"))
    assert [member.member_id for member in library.members] == ["M-00", "M-01"]


def test_loans_starts_empty():
    assert a_library().loans == ()


# --------------------------------------------------------------------------- #
# Library: books
# --------------------------------------------------------------------------- #
def test_add_book_returns_the_book():
    library = Library("L")
    assert library.add_book(a_book()).isbn == CLEAN


def test_add_book_refuses_a_duplicate():
    library = a_library()
    with pytest.raises(DuplicateBook, match="already on the shelf"):
        library.add_book(a_book(title="Second"))


def test_add_book_refuses_a_non_book():
    with pytest.raises(LibraryError, match="only a Book"):
        Library("L").add_book(CLEAN)


def test_book_looks_a_title_up():
    assert a_library().book(CLEAN).title == "Book 884"


def test_book_normalises_hyphens():
    assert a_library().book("978-0-13-235088-4").isbn == CLEAN


def test_book_refuses_an_unknown_isbn():
    with pytest.raises(LibraryError, match="no book with ISBN"):
        a_library().book(REFACTORING)


def test_book_refuses_an_invalid_isbn():
    with pytest.raises(LibraryError, match="not a valid ISBN"):
        a_library().book("abcde")


def test_remove_book_drops_the_title():
    library = a_library((CLEAN, 3))
    assert library.remove_book(CLEAN).isbn == CLEAN and len(library) == 0


def test_remove_book_refuses_a_title_on_loan():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    with pytest.raises(LibraryError, match="on loan, starting with M-01"):
        library.remove_book(CLEAN)
    assert len(library) == 2


def test_remove_book_refuses_an_unknown_isbn():
    with pytest.raises(LibraryError, match="no book with ISBN"):
        a_library().remove_book(REFACTORING)


def test_set_copies_grows_the_shelf():
    assert a_library().set_copies(CLEAN, 5).copies == 5


def test_set_copies_accepts_the_number_on_loan():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    assert library.set_copies(CLEAN, 1).copies == 1


def test_set_copies_refuses_a_shrink_below_the_loans():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    with pytest.raises(LibraryError, match="1 are on loan"):
        library.set_copies(CLEAN, 0)
    assert library.book(CLEAN).copies == 3


def test_set_copies_names_the_current_copy_count():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    with pytest.raises(LibraryError, match="owns 3 copies"):
        library.set_copies(CLEAN, 0)


def test_set_copies_refuses_a_negative():
    with pytest.raises(LibraryError, match="must not be negative"):
        a_library().set_copies(CLEAN, -1)


def test_search_matches_the_title():
    library = a_library()
    library.add_book(Book(REFACTORING, "Refactoring", "Martin Fowler", 1))
    assert [book.isbn for book in library.search("refactoring")] == \
        [REFACTORING]


def test_search_matches_the_author():
    library = a_library()
    library.add_book(Book(REFACTORING, "Refactoring", "Martin Fowler", 1))
    assert [book.isbn for book in library.search("fowler")] == [REFACTORING]


def test_search_matches_the_isbn():
    assert [book.isbn for book in a_library().search("0884")] == [CLEAN]


def test_search_is_case_insensitive():
    library = a_library()
    library.add_book(Book(REFACTORING, "Refactoring", "Martin Fowler", 1))
    assert len(library.search("FOWLER")) == 1


def test_search_returns_every_match():
    library = a_library()
    assert len(library.search("book")) == 2


def test_search_returns_nothing_for_no_match():
    assert a_library().search("nothing") == []


def test_search_needs_text():
    with pytest.raises(LibraryError, match="needs text"):
        a_library().search(7)


def test_search_needs_something_to_look_for():
    with pytest.raises(LibraryError, match="something to look for"):
        a_library().search("   ")


# --------------------------------------------------------------------------- #
# Library: members
# --------------------------------------------------------------------------- #
def test_add_member_returns_the_member():
    library = Library("L")
    assert library.add_member(Member("M-01", "Asha")).member_id == "M-01"


def test_add_member_trims_the_id_and_name():
    library = Library("L")
    member = library.add_member(Member("  M-01 ", "  Asha Rao  "))
    assert (member.member_id, member.name) == ("M-01", "Asha Rao")


def test_add_member_refuses_a_duplicate():
    library = a_library()
    with pytest.raises(DuplicateMember, match="already registered"):
        library.add_member(Member(" M-01 ", "Someone Else"))


def test_add_member_refuses_a_non_member():
    with pytest.raises(LibraryError, match="only a Member"):
        Library("L").add_member("M-01")


def test_member_looks_a_reader_up():
    assert a_library().member("M-01").name == "Asha Rao"


def test_member_trims_the_lookup():
    assert a_library().member("  M-01  ").name == "Asha Rao"


def test_member_refuses_an_unknown_id():
    with pytest.raises(LibraryError, match="no member with id"):
        a_library().member("M-99")


def test_member_refuses_a_non_string_id():
    with pytest.raises(LibraryError, match="must be text"):
        a_library().member(1)


def test_open_loans_of_a_new_member_is_empty():
    assert a_library().open_loans_of("M-01") == ()


def test_open_loans_of_refuses_an_unknown_member():
    with pytest.raises(LibraryError, match="no member with id"):
        a_library().open_loans_of("M-99")


# --------------------------------------------------------------------------- #
# Library: derived counts
# --------------------------------------------------------------------------- #
def test_available_equals_copies_before_any_loan():
    assert a_library().available(CLEAN) == 3


def test_on_loan_is_zero_before_any_loan():
    assert a_library().on_loan(CLEAN) == 0


def test_a_book_is_not_issued_before_any_loan():
    assert a_library().issued(CLEAN) is False


def test_one_loan_lowers_available():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    assert library.available(CLEAN) == 2


def test_one_loan_makes_the_book_issued():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    assert library.issued(CLEAN) is True


def test_on_loan_counts_every_copy_out():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    library.add_member(Member("M-02", "Bilal"))
    library.borrow(CLEAN, "M-02", DAY)
    assert library.on_loan(CLEAN) == 2 and library.available(CLEAN) == 1


def test_a_returned_loan_stops_counting():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    library.give_back(CLEAN, "M-01", "2026-03-12")
    assert library.on_loan(CLEAN) == 0 and library.available(CLEAN) == 3
    assert library.issued(CLEAN) is False


# --------------------------------------------------------------------------- #
# Library: borrowing
# --------------------------------------------------------------------------- #
def test_borrow_creates_an_open_loan():
    loan = a_library().borrow(CLEAN, "M-01", DAY)
    assert loan.is_open and loan.isbn == CLEAN and loan.member_id == "M-01"


def test_borrow_sets_the_due_date():
    assert a_library().borrow(CLEAN, "M-01", DAY).due == date(2026, 3, 24)


def test_borrow_records_the_loan_on_the_library():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    assert len(library.loans) == 1 and len(library.open_loans) == 1


def test_borrow_refuses_an_empty_shelf():
    library = a_library((GOOD_PARTS, 1))
    library.borrow(GOOD_PARTS, "M-01", DAY)
    with pytest.raises(NoCopiesLeft, match="already out"):
        library.borrow(GOOD_PARTS, "M-01", "2026-03-11")


def test_borrow_refuses_a_duplicate_for_the_same_member():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    with pytest.raises(LibraryError, match="already has .* on loan"):
        library.borrow(CLEAN, "M-01", "2026-03-11")


def test_borrow_allows_the_same_book_to_two_members():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    library.add_member(Member("M-02", "Bilal"))
    assert library.borrow(CLEAN, "M-02", DAY).member_id == "M-02"


def test_borrow_refuses_the_book_past_the_limit():
    library = a_library((CLEAN, 5), (GOOD_PARTS, 1), (REFACTORING, 1))
    library.add_member(Member("M-02", "Bilal", 2))
    library.borrow(CLEAN, "M-02", DAY)
    library.borrow(GOOD_PARTS, "M-02", DAY)
    with pytest.raises(LoanLimitReached, match="2 of 2 allowed"):
        library.borrow(REFACTORING, "M-02", DAY)


def test_the_limit_counts_only_open_loans():
    library = a_library((CLEAN, 5), (GOOD_PARTS, 1), (REFACTORING, 1))
    library.add_member(Member("M-02", "Bilal", 2))
    library.borrow(CLEAN, "M-02", DAY)
    library.borrow(GOOD_PARTS, "M-02", DAY)
    library.give_back(GOOD_PARTS, "M-02", "2026-03-11")
    assert library.borrow(REFACTORING, "M-02", DAY).isbn == REFACTORING


def test_borrow_refuses_an_unknown_isbn():
    with pytest.raises(LibraryError, match="no book with ISBN"):
        a_library().borrow(REFACTORING, "M-01", DAY)


def test_borrow_refuses_an_unknown_member():
    with pytest.raises(LibraryError, match="no member with id"):
        a_library().borrow(CLEAN, "M-99", DAY)


def test_borrow_refuses_a_bad_date():
    with pytest.raises(LibraryError):
        a_library().borrow(CLEAN, "M-01", "2026-3-10")


def test_borrow_refuses_a_date_that_does_not_exist():
    with pytest.raises(LibraryError, match="not a real date"):
        a_library().borrow(CLEAN, "M-01", "2026-02-30")


# --------------------------------------------------------------------------- #
# Library: returning
# --------------------------------------------------------------------------- #
def test_give_back_closes_the_loan():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    loan, fine = library.give_back(CLEAN, "M-01", "2026-03-12")
    assert not loan.is_open and loan.returned == date(2026, 3, 12)
    assert fine == 0


def test_give_back_charges_for_the_late_days():
    library = a_library()
    library.borrow(CLEAN, "M-01", "2026-03-02")
    loan, fine = library.give_back(CLEAN, "M-01", "2026-03-20")
    assert loan.days_late() == 4 and fine == 100


def test_give_back_charges_nothing_on_the_due_date():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    assert library.give_back(CLEAN, "M-01", "2026-03-24")[1] == 0


def test_give_back_frees_the_copy():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    library.give_back(CLEAN, "M-01", "2026-03-12")
    assert library.available(CLEAN) == 3


def test_give_back_refuses_a_loan_that_is_not_open():
    with pytest.raises(LibraryError, match="no open loan"):
        a_library().give_back(CLEAN, "M-01", "2026-03-12")


def test_give_back_refuses_the_wrong_member():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    library.add_member(Member("M-02", "Bilal"))
    with pytest.raises(LibraryError, match="M-02 has no open loan"):
        library.give_back(CLEAN, "M-02", "2026-03-12")


def test_give_back_refuses_a_second_return():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    library.give_back(CLEAN, "M-01", "2026-03-12")
    with pytest.raises(LibraryError, match="no open loan"):
        library.give_back(CLEAN, "M-01", "2026-03-13")


def test_give_back_refuses_a_date_before_the_borrow():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    with pytest.raises(LibraryError, match="before it was borrowed"):
        library.give_back(CLEAN, "M-01", "2026-03-09")


# --------------------------------------------------------------------------- #
# Library: overdue and fines
# --------------------------------------------------------------------------- #
def test_overdue_is_empty_on_the_due_date():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    assert library.overdue("2026-03-24") == []


def test_overdue_lists_a_late_loan():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    assert [loan.isbn for loan in library.overdue("2026-03-25")] == [CLEAN]


def test_overdue_skips_a_returned_loan():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    library.give_back(CLEAN, "M-01", "2026-03-20")
    assert library.overdue("2026-03-30") == []


def test_overdue_orders_by_due_date():
    library = a_library((CLEAN, 1), (GOOD_PARTS, 1))
    library.borrow(GOOD_PARTS, "M-01", "2026-03-01")
    library.add_member(Member("M-02", "Bilal"))
    library.borrow(CLEAN, "M-02", "2026-03-05")
    assert [loan.isbn for loan in library.overdue("2026-03-25")] == \
        [GOOD_PARTS, CLEAN]


def test_overdue_refuses_a_bad_date():
    with pytest.raises(LibraryError, match="not a real date"):
        a_library().overdue("2026-02-30")


def test_fines_is_empty_when_nothing_is_late():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    assert library.fines("2026-03-20") == {}


def test_fines_totals_per_member():
    library = a_library((CLEAN, 1), (GOOD_PARTS, 1))
    library.borrow(GOOD_PARTS, "M-01", "2026-03-01")   # due 03-15
    library.add_member(Member("M-02", "Bilal"))
    library.borrow(CLEAN, "M-02", "2026-03-05")        # due 03-19
    assert library.fines("2026-03-20") == {"M-01": 125, "M-02": 25}


def test_fines_are_sorted_by_member():
    library = a_library((CLEAN, 1), (GOOD_PARTS, 1))
    library.borrow(CLEAN, "M-01", "2026-03-01")
    library.add_member(Member("M-02", "Bilal"))
    library.borrow(GOOD_PARTS, "M-02", "2026-03-01")
    assert list(library.fines("2026-03-20")) == ["M-01", "M-02"]


def test_total_fine_sums_the_members():
    library = a_library((CLEAN, 1), (GOOD_PARTS, 1))
    library.borrow(CLEAN, "M-01", "2026-03-01")
    library.add_member(Member("M-02", "Bilal"))
    library.borrow(GOOD_PARTS, "M-02", "2026-03-05")
    # M-01 is due 03-15 (5 days late), M-02 is due 03-19 (1 day late)
    assert library.total_fine("2026-03-20") == 150


def test_total_fine_is_zero_for_a_clean_shelf():
    assert a_library().total_fine(DAY) == 0


# --------------------------------------------------------------------------- #
# Library: consistency
# --------------------------------------------------------------------------- #
def test_a_new_library_is_consistent():
    library = a_library()
    assert len(library.consistency()) == 5
    assert all(passed for _, passed in library.consistency())
    assert library.problems() == []


def test_consistency_names_its_checks():
    names = [name for name, _ in a_library().consistency()]
    assert "no book has negative copies" in names
    assert "no book has more copies out than it owns" in names
    assert "no member is over their limit" in names
    assert "every loan is due 14 days after it was borrowed" in names


def test_consistency_catches_negative_copies():
    library = a_library()
    library.book(CLEAN)._copies = -1
    assert "no book has negative copies" in library.problems()


def test_consistency_catches_more_loans_than_copies():
    library = a_library((GOOD_PARTS, 1))
    library.borrow(GOOD_PARTS, "M-01", DAY)
    library._loans.append(Loan.of(GOOD_PARTS, "M-01", "2026-03-11"))
    assert "no book has more copies out than it owns" in library.problems()


def test_consistency_accepts_as_many_loans_as_copies():
    library = a_library((GOOD_PARTS, 1))
    library.borrow(GOOD_PARTS, "M-01", DAY)
    assert "no book has more copies out than it owns" not in \
        library.problems()


def test_consistency_catches_a_loan_for_an_unknown_book():
    library = a_library()
    library._loans.append(Loan.of(REFACTORING, "M-01", DAY))
    assert "every open loan names a book and a member on record" in \
        library.problems()


def test_consistency_catches_a_loan_for_an_unknown_member():
    library = a_library()
    library._loans.append(Loan.of(CLEAN, "M-99", DAY))
    assert "every open loan names a book and a member on record" in \
        library.problems()


def test_consistency_catches_a_wrong_due_date():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    object.__setattr__(library.loans[0], "due", date(2026, 1, 1))
    assert "every loan is due 14 days after it was borrowed" in \
        library.problems()


def test_consistency_catches_a_member_over_their_limit():
    library = a_library((CLEAN, 4), (GOOD_PARTS, 1))
    library.add_member(Member("M-02", "Bilal", 1))
    library.borrow(CLEAN, "M-02", DAY)
    library._loans.append(Loan.of(GOOD_PARTS, "M-02", "2026-03-11"))
    assert library.problems() == ["no member is over their limit"]


def test_consistency_is_repeatable():
    library = a_library()
    assert library.consistency() == library.consistency()


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def test_a_library_round_trips():
    library = a_library()
    library.borrow(CLEAN, "M-01", DAY)
    library.give_back(CLEAN, "M-01", "2026-03-12")
    copy = Library.from_dict(library.to_dict())
    assert copy.to_dict() == library.to_dict()
    assert copy.available(CLEAN) == library.available(CLEAN)


def test_a_library_dict_keeps_the_name():
    assert a_library().to_dict()["name"] == "Test Library"


def test_library_from_dict_refuses_a_non_object():
    with pytest.raises(LibraryError, match="must be an object"):
        Library.from_dict([])


def test_library_from_dict_refuses_an_unknown_key():
    with pytest.raises(LibraryError, match="unknown library keys"):
        Library.from_dict({"name": "x", "books": [], "members": [],
                           "loans": [], "extra": 1})


def test_library_from_dict_requires_the_loans():
    with pytest.raises(LibraryError, match="missing 'loans'"):
        Library.from_dict({"name": "x", "books": [], "members": []})


def test_library_from_dict_requires_lists():
    with pytest.raises(LibraryError, match="'books' must be a list"):
        Library.from_dict({"name": "x", "books": {}, "members": [],
                           "loans": []})


def test_library_from_dict_refuses_a_non_object_book():
    with pytest.raises(LibraryError, match="a book must be an object"):
        Library.from_dict({"name": "x", "books": [[]], "members": [],
                           "loans": []})


def test_library_from_dict_refuses_a_duplicate_isbn():
    payload = a_library().to_dict()
    payload["books"].append(payload["books"][0])
    with pytest.raises(DuplicateBook):
        Library.from_dict(payload)


def test_library_from_dict_refuses_a_duplicate_member():
    payload = a_library().to_dict()
    payload["members"].append(payload["members"][0])
    with pytest.raises(DuplicateMember):
        Library.from_dict(payload)


def test_library_from_dict_refuses_a_loan_for_an_unknown_book():
    payload = a_library().to_dict()
    payload["loans"].append(Loan.of(REFACTORING, "M-01", DAY).to_dict())
    with pytest.raises(LibraryError, match="no book with ISBN"):
        Library.from_dict(payload)


def test_library_from_dict_refuses_a_loan_for_an_unknown_member():
    payload = a_library().to_dict()
    payload["loans"].append(Loan.of(CLEAN, "M-99", DAY).to_dict())
    with pytest.raises(LibraryError, match="no member with id"):
        Library.from_dict(payload)


def test_the_data_file_is_named_for_its_purpose():
    assert DATA_FILE.name == "library.json"
    assert DATA_FILE.parent.name == "data"


def test_the_seeded_library_loads():
    seeded = load_library()
    assert seeded.name == "Riverside Library"


def test_the_seeded_counts_are_pinned():
    seeded = load_library()
    assert len(seeded) == 6 and seeded.total_copies == 10
    assert len(seeded.members) == 3
    assert len(seeded.loans) == 5 and len(seeded.open_loans) == 4


def test_the_seeded_library_is_consistent():
    assert load_library().problems() == []


def test_the_seeded_availability_is_pinned():
    seeded = load_library()
    assert seeded.available(CLEAN) == 2
    assert seeded.available(GOOD_PARTS) == 0
    assert seeded.available(PRAGMATIC) == 2


def test_the_seeded_issued_titles_are_pinned():
    seeded = load_library()
    assert seeded.issued(GOOD_PARTS) is True
    assert seeded.issued(PRAGMATIC) is False


def test_the_seeded_overdue_loan_is_pinned():
    late = load_library().overdue(DAY)
    assert len(late) == 1
    assert late[0].isbn == GOOD_PARTS and late[0].member_id == "M-02"
    assert late[0].days_late(DAY) == 4


def test_the_seeded_fine_is_pinned():
    seeded = load_library()
    assert seeded.fines(DAY) == {"M-02": 100}
    assert seeded.total_fine(DAY) == 100


def test_the_seeded_returned_loan_is_closed():
    closed = [loan for loan in load_library().loans if not loan.is_open]
    assert len(closed) == 1 and closed[0].isbn == PRAGMATIC
    assert closed[0].returned == date(2026, 3, 4)


def test_the_seeded_isbn_10_title_is_on_the_shelf():
    assert load_library().book(KNUTH).copies == 1


def test_the_seeded_member_limits_are_pinned():
    limits = {member.member_id: member.limit
              for member in load_library().members}
    assert limits == {"M-01": 3, "M-02": 2, "M-03": 3}


def test_load_library_refuses_a_missing_file(tmp_path):
    with pytest.raises(LibraryError, match="not found"):
        load_library(tmp_path / "nope.json")


def test_load_library_refuses_invalid_json(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(LibraryError, match="not valid JSON"):
        load_library(path)


def test_save_library_writes_a_readable_file(tmp_path):
    seeded = load_library()
    target = tmp_path / "out.json"
    save_library(target, seeded)
    assert load_library(target).to_dict() == seeded.to_dict()


def test_save_library_returns_the_path(tmp_path):
    target = tmp_path / "out.json"
    assert save_library(target, Library("L")) == target


def test_save_library_creates_directories(tmp_path):
    target = tmp_path / "a" / "b" / "library.json"
    save_library(target, Library("L"))
    assert target.is_file()


def test_save_library_ends_with_a_newline(tmp_path):
    target = tmp_path / "out.json"
    save_library(target, Library("L"))
    assert target.read_text(encoding="utf-8").endswith("}\n")


def test_save_library_is_byte_identical_on_a_second_save(tmp_path):
    target = tmp_path / "out.json"
    seeded = load_library()
    save_library(target, seeded)
    first = target.read_bytes()
    save_library(target, load_library(target))
    assert target.read_bytes() == first


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_shows_the_isbn_defect(capsys):
    run_demo()
    assert "accepted 'abcde'" in capsys.readouterr().out


def test_demo_shows_the_drift(capsys):
    run_demo()
    assert "the record implies 1 out while 2 loans are still open" in \
        capsys.readouterr().out


def test_demo_shows_the_shared_attribute(capsys):
    run_demo()
    assert "['Dune']" in capsys.readouterr().out


def test_demo_shows_the_seeded_counts(capsys):
    run_demo()
    assert "6 titles, 10 copies, 3 members" in capsys.readouterr().out


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert all(ord(character) < 128 for character in out)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_shelf(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "6 titles, 10 copies, 4 on loan" in out
    assert CLEAN in out


def test_cli_books_flag_does_the_same(capsys):
    assert cli.main(["--books"]) == 0
    assert "6 titles" in capsys.readouterr().out


def test_cli_search(capsys):
    assert cli.main(["--search", "crockford"]) == 0
    out = capsys.readouterr().out
    assert "1 title(s) match 'crockford'" in out


def test_cli_available(capsys):
    assert cli.main(["--available", GOOD_PARTS]) == 0
    out = capsys.readouterr().out
    assert "1 owned, 1 out, 0 on the shelf" in out


def test_cli_available_refuses_an_unknown_isbn(capsys):
    assert cli.main(["--available", "9780262033848"]) == 2
    assert "no book with ISBN" in capsys.readouterr().err


def test_cli_member_lists_the_loans(capsys):
    assert cli.main(["--member", "M-01"]) == 0
    out = capsys.readouterr().out
    assert "M-01  Asha Rao  2 of 3 allowed" in out
    assert "2026-03-16" in out


def test_cli_member_refuses_an_unknown_id(capsys):
    assert cli.main(["--member", "M-99"]) == 2
    assert "no member with id" in capsys.readouterr().err


def test_cli_borrow(capsys):
    assert cli.main(["--borrow", f"{PRAGMATIC}:M-03:{DAY}"]) == 0
    out = capsys.readouterr().out
    assert "borrowed 2026-03-10, due 2026-03-24 (14 days)" in out


def test_cli_borrow_refuses_an_empty_shelf(capsys):
    assert cli.main(["--borrow", f"{GOOD_PARTS}:M-03:{DAY}"]) == 2
    assert "already out" in capsys.readouterr().err


def test_cli_borrow_refuses_a_malformed_spec(capsys):
    assert cli.main(["--borrow", PRAGMATIC]) == 2
    assert "expected ISBN:MEMBER:YYYY-MM-DD" in capsys.readouterr().err


def test_cli_return(capsys):
    assert cli.main(["--return", f"{GOOD_PARTS}:M-02:{DAY}"]) == 0
    out = capsys.readouterr().out
    assert "4 day(s) late, fine Rs 1.00" in out


def test_cli_return_refuses_a_loan_that_is_not_open(capsys):
    assert cli.main(["--return", f"{PRAGMATIC}:M-01:{DAY}"]) == 2
    assert "has no open loan" in capsys.readouterr().err


def test_cli_overdue(capsys):
    assert cli.main(["--overdue"]) == 0
    out = capsys.readouterr().out
    assert "1 overdue, Rs 1.00 owed" in out
    assert "4 day(s) late" in out


def test_cli_overdue_later_on(capsys):
    assert cli.main(["--overdue", "--on", "2026-03-20"]) == 0
    out = capsys.readouterr().out
    assert "3 overdue, Rs 4.75 owed" in out


def test_cli_fines(capsys):
    assert cli.main(["--fines"]) == 0
    out = capsys.readouterr().out
    assert "M-02" in out and "Rs 1.00" in out


def test_cli_fines_on_a_later_date(capsys):
    assert cli.main(["--fines", "--on", "2026-03-20"]) == 0
    out = capsys.readouterr().out
    assert "Rs 1.25" in out and "Rs 3.50" in out


def test_cli_fines_refuses_a_bad_date(capsys):
    assert cli.main(["--fines", "--on", "2026-13-01"]) == 2
    assert "not a real date" in capsys.readouterr().err


def test_cli_add_book(capsys):
    assert cli.main(["--add-book",
                     "9780262033848:CLRS:Thomas Cormen:2"]) == 0
    out = capsys.readouterr().out
    assert "added 9780262033848  CLRS  x2" in out


def test_cli_add_book_refuses_a_bad_isbn(capsys):
    assert cli.main(["--add-book", "abcde:Book:Author:1"]) == 2
    assert "not a valid ISBN" in capsys.readouterr().err


def test_cli_add_book_refuses_a_duplicate(capsys):
    assert cli.main(["--add-book", f"{CLEAN}:Second:Author:1"]) == 2
    assert "already on the shelf" in capsys.readouterr().err


def test_cli_add_book_refuses_a_bad_copy_count(capsys):
    assert cli.main(["--add-book", "9780262033848:CLRS:Cormen:many"]) == 2
    assert "not a whole number" in capsys.readouterr().err


def test_cli_copies(capsys):
    assert cli.main(["--copies", f"{CLEAN}:4"]) == 0
    assert "now owns 4 copies, 1 on loan" in capsys.readouterr().out


def test_cli_copies_refuses_a_shrink_below_the_loans(capsys):
    assert cli.main(["--copies", f"{CLEAN}:0"]) == 2
    assert "cannot own only 0" in capsys.readouterr().err


def test_cli_consistency(capsys):
    assert cli.main(["--consistency"]) == 0
    assert "5/5 checks passed" in capsys.readouterr().out


def test_cli_legacy(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "len(value.strip()) >= 5" in out
    assert "issued = Column(Boolean, default=False)" in out
    assert "books = []" in out


def test_cli_json_books(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "books" and len(payload["books"]) == 6
    assert payload["books"][0]["isbn"] == KNUTH


def test_cli_json_available(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--available", GOOD_PARTS, "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["copies"] == 1 and payload["on_loan"] == 1
    assert payload["available"] == 0 and payload["issued"] is True


def test_cli_json_overdue(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--overdue", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["count"] == 1 and payload["total_cents"] == 100
    assert payload["loans"][0]["days_late"] == 4


def test_cli_json_consistency(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--consistency", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["clean"] is True and len(payload["checks"]) == 5


def test_cli_write_saves_the_loan(tmp_path, capsys):
    target = tmp_path / "saved.json"
    assert cli.main(["--borrow", f"{PRAGMATIC}:M-03:{DAY}",
                     "--write", str(target)]) == 0
    capsys.readouterr()
    assert len(load_library(target).open_loans) == 5


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.json"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--fines", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
