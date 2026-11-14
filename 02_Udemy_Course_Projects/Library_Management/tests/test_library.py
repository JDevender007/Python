"""Tests for Library_Management: legacy format, money, loans, storage, CLI."""

from __future__ import annotations

import datetime
import json
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from library import (                                     # noqa: E402
    AS_OF,
    DATA_FILE,
    FINE_CAP_CENTS,
    FINE_PER_DAY_CENTS,
    LEGACY_FORMAT,
    LEGACY_RECORD_SIZE,
    LOAN_DAYS,
    Book,
    Catalog,
    LibraryError,
    Loan,
    format_money,
    legacy_delete_keeps,
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

DAY = datetime.date
ISBN = "978-0132350884"


def book(isbn=ISBN, title="Clean Code", author="Robert C. Martin",
         cents=4250, total=1, available=None):
    return Book(isbn, title, author, cents, total,
                total if available is None else available)


@pytest.fixture()
def catalog() -> Catalog:
    catalog = Catalog()
    catalog.add_new(ISBN, "Clean Code", "Robert C. Martin", "42.50", 2)
    catalog.add_new("978-0134757599", "Refactoring", "Martin Fowler", "47.20")
    return catalog


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
def test_parse_money_of_a_string():
    assert parse_money("19.99") == 1999


def test_parse_money_of_a_float():
    assert parse_money(19.99) == 1999


def test_parse_money_of_a_whole_int_is_whole_currency():
    assert parse_money(19) == 1900


def test_parse_money_of_zero():
    assert parse_money("0.00") == 0


def test_parse_money_of_one_cent():
    assert parse_money("0.01") == 1


def test_parse_money_ignores_surrounding_space():
    assert parse_money(" 5.50 ") == 550


@pytest.mark.parametrize("bad", ["19.999", "0.0001", "-1", "-0.01", "abc",
                                 "", "nan", "inf"])
def test_parse_money_refuses_bad_values(bad):
    with pytest.raises(LibraryError):
        parse_money(bad)


def test_parse_money_refuses_a_boolean():
    with pytest.raises(LibraryError, match="boolean"):
        parse_money(True)


def test_parse_money_refuses_a_negative_int():
    with pytest.raises(LibraryError, match="negative"):
        parse_money(-5)


def test_format_money_pads_the_cents():
    assert format_money(1999) == "19.99"
    assert format_money(5) == "0.05"


def test_format_money_groups_thousands():
    assert format_money(12345600) == "123,456.00"


def test_format_money_of_zero():
    assert format_money(0) == "0.00"


def test_format_money_of_a_negative():
    assert format_money(-125) == "-1.25"


def test_format_money_refuses_a_non_integer():
    with pytest.raises(LibraryError):
        format_money("1.00")


def test_money_round_trips():
    for text in ("0.01", "19.99", "1234.50"):
        assert format_money(parse_money(text)) == \
            f"{float(text):,.2f}"


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
def test_parse_date_accepts_iso():
    assert parse_date("2024-04-15") == DAY(2024, 4, 15)


def test_parse_date_accepts_a_date():
    assert parse_date(DAY(2024, 4, 15)) == DAY(2024, 4, 15)


def test_parse_date_accepts_a_datetime():
    assert parse_date(datetime.datetime(2024, 4, 15, 9, 0)) == DAY(2024, 4, 15)


@pytest.mark.parametrize("bad", ["2024-4-5", "15/04/2024", "2024-02-30",
                                 "April", ""])
def test_parse_date_refuses_non_iso(bad):
    with pytest.raises(LibraryError):
        parse_date(bad)


def test_parse_date_refuses_a_non_string():
    with pytest.raises(LibraryError, match="must be a string"):
        parse_date(20240415)


# --------------------------------------------------------------------------- #
# The legacy binary format
# --------------------------------------------------------------------------- #
def test_legacy_record_size():
    assert LEGACY_RECORD_SIZE == struct.calcsize(LEGACY_FORMAT) == 60


def test_legacy_pack_is_one_record_long():
    assert len(legacy_pack(1, "T", "A", 1.0)) == LEGACY_RECORD_SIZE


def test_legacy_price_is_mangled_by_float32():
    recovered = legacy_unpack(legacy_pack(1, "T", "A", 19.99))["price"]
    assert recovered != 19.99
    assert abs(recovered - 19.99) < 0.001


def test_legacy_round_trip_of_a_short_title():
    assert legacy_unpack(legacy_pack(3, "Dune", "Herbert", 9.5))["title"] == \
        "Dune"


def test_legacy_truncates_a_long_title_silently():
    title = "An Extremely Long Title That Will Not Fit In Thirty Bytes"
    stored = legacy_unpack(legacy_pack(4, title, "A", 1.0))["title"]
    assert len(stored) == 30
    assert title.startswith(stored)
    assert stored != title


def test_legacy_slice_can_cut_utf8_mid_character():
    title = "a" + "e\u0301" * 20
    sliced = title.strip().encode()[:30]
    with pytest.raises(UnicodeDecodeError):
        sliced.decode()


def test_legacy_valid_utf8_still_round_trips():
    assert legacy_unpack(legacy_pack(5, "caf\u00e9", "A", 1.0))["title"] == \
        "caf\u00e9"


def test_legacy_readlines_splits_on_byte_ten():
    record = legacy_pack(10, "Book", "Author", 1.0)
    assert b"\n" in record
    chunks = legacy_readlines_split(record)
    assert len(chunks) == 2
    assert all(len(chunk) != LEGACY_RECORD_SIZE for chunk in chunks)


def test_legacy_readlines_leaves_a_safe_record_whole():
    record = legacy_pack(11, "Other", "A", 2.0)
    assert b"\n" not in record
    assert legacy_readlines_split(record) == [record]


def test_legacy_delete_drops_the_split_chunks():
    record = legacy_pack(10, "Book", "Author", 1.0)
    chunks = legacy_readlines_split(record)
    assert legacy_delete_keeps(chunks, 99) == []


def test_legacy_delete_keeps_a_healthy_neighbour():
    risky = legacy_pack(10, "Book", "Author", 1.0)
    healthy = legacy_pack(11, "Other", "A", 2.0)
    kept = legacy_delete_keeps(legacy_readlines_split(risky) + [healthy], 99)
    assert kept == [healthy]


def test_legacy_delete_removes_the_requested_id():
    first = legacy_pack(1, "One", "A", 1.0)
    second = legacy_pack(2, "Two", "B", 2.0)
    assert legacy_delete_keeps([first, second], 1) == [second]


def test_legacy_append_allows_duplicate_ids():
    twice = legacy_pack(7, "Dune", "Frank Herbert", 9.99) * 2
    ids = [legacy_unpack(twice[index:index + LEGACY_RECORD_SIZE])["id"]
           for index in range(0, len(twice), LEGACY_RECORD_SIZE)]
    assert ids == [7, 7]


# --------------------------------------------------------------------------- #
# Book
# --------------------------------------------------------------------------- #
def test_book_trims_text():
    item = Book(" X ", " T ", " A ", 100)
    assert (item.isbn, item.title, item.author) == ("X", "T", "A")


def test_book_defaults_to_one_available_copy():
    item = Book("X", "T", "A", 100)
    assert item.copies_total == 1 and item.copies_available == 1


def test_book_on_loan_is_derived():
    assert Book("X", "T", "A", 100, 3, 1).on_loan == 2


def test_book_refuses_a_blank_isbn():
    with pytest.raises(LibraryError, match="isbn must not be empty"):
        Book("  ", "T", "A", 100)


def test_book_refuses_a_non_string_title():
    with pytest.raises(LibraryError, match="title must be a string"):
        Book("X", 7, "A", 100)


def test_book_refuses_zero_copies():
    with pytest.raises(LibraryError, match="at least 1"):
        Book("X", "T", "A", 100, 0, 0)


def test_book_refuses_available_above_total():
    with pytest.raises(LibraryError, match="outside"):
        Book("X", "T", "A", 100, 1, 2)


def test_book_refuses_a_non_integer_price():
    with pytest.raises(LibraryError, match="price_cents"):
        Book("X", "T", "A", 4.25)                           # type: ignore[arg-type]


def test_book_refuses_a_negative_price():
    with pytest.raises(LibraryError, match="negative"):
        Book("X", "T", "A", -1)


def test_book_dict_round_trip():
    item = Book("X", "T", "A", 999, 3, 2)
    assert Book.from_dict(item.to_dict()) == item


def test_book_from_dict_defaults_copies():
    item = Book.from_dict({"isbn": "X", "title": "T", "author": "A",
                           "price_cents": 100})
    assert item.copies_total == 1 and item.copies_available == 1


def test_book_from_dict_refuses_a_missing_field():
    with pytest.raises(LibraryError, match="missing author"):
        Book.from_dict({"isbn": "X", "title": "T", "price_cents": 1})


def test_book_from_dict_refuses_an_unknown_field():
    with pytest.raises(LibraryError, match="unknown field"):
        Book.from_dict({"isbn": "X", "title": "T", "author": "A",
                        "price_cents": 1, "shelf": 3})


def test_book_from_dict_refuses_a_non_object():
    with pytest.raises(LibraryError, match="JSON object"):
        Book.from_dict([1, 2])


def test_book_is_frozen():
    with pytest.raises(Exception):
        book().title = "New"                                # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Loan
# --------------------------------------------------------------------------- #
def test_loan_is_open_until_returned():
    assert Loan(ISBN, "asha", "2024-04-01", "2024-04-15").open is True
    assert Loan(ISBN, "asha", "2024-04-01", "2024-04-15",
                "2024-04-10").open is False


def test_loan_refuses_a_due_date_before_it_was_borrowed():
    with pytest.raises(LibraryError, match="after borrowed"):
        Loan(ISBN, "asha", "2024-04-10", "2024-04-10")


def test_loan_refuses_a_return_before_the_borrow():
    with pytest.raises(LibraryError, match="precede"):
        Loan(ISBN, "asha", "2024-04-10", "2024-04-24", "2024-04-09")


def test_loan_refuses_a_blank_member():
    with pytest.raises(LibraryError, match="member must not be empty"):
        Loan(ISBN, "  ", "2024-04-01", "2024-04-15")


def test_days_late_is_zero_before_the_due_date():
    assert Loan(ISBN, "a", "2024-04-01", "2024-04-15").days_late(
        "2024-04-14") == 0


def test_days_late_is_zero_on_the_due_date():
    assert Loan(ISBN, "a", "2024-04-01", "2024-04-15").days_late(
        "2024-04-15") == 0


def test_days_late_counts_after_the_due_date():
    assert Loan(ISBN, "a", "2024-04-01", "2024-04-15").days_late(
        "2024-04-21") == 6


def test_a_returned_loan_measures_lateness_at_the_return():
    loan = Loan(ISBN, "a", "2024-04-01", "2024-04-15", "2024-04-18")
    assert loan.days_late("2024-05-01") == 3


def test_fine_is_per_day():
    loan = Loan(ISBN, "a", "2024-04-01", "2024-04-15")
    assert loan.fine_cents("2024-04-20") == 5 * FINE_PER_DAY_CENTS


def test_fine_is_zero_when_on_time():
    assert Loan(ISBN, "a", "2024-04-01", "2024-04-15").fine_cents(
        "2024-04-15") == 0


def test_fine_is_capped():
    loan = Loan(ISBN, "a", "2024-01-01", "2024-01-15", "2024-12-31")
    assert loan.fine_cents("2024-12-31") == FINE_CAP_CENTS


def test_loan_dict_round_trip():
    loan = Loan(ISBN, "a", "2024-04-01", "2024-04-15", "2024-04-18")
    assert Loan.from_dict(loan.to_dict()) == loan


def test_loan_dict_keeps_a_null_return():
    loan = Loan(ISBN, "a", "2024-04-01", "2024-04-15")
    assert Loan.from_dict(loan.to_dict()).returned_on is None


def test_loan_from_dict_refuses_a_missing_field():
    with pytest.raises(LibraryError, match="missing due_on"):
        Loan.from_dict({"isbn": ISBN, "member": "a",
                        "borrowed_on": "2024-04-01"})


def test_loan_from_dict_refuses_an_unknown_field():
    with pytest.raises(LibraryError, match="unknown field"):
        Loan.from_dict({"isbn": ISBN, "member": "a",
                        "borrowed_on": "2024-04-01", "due_on": "2024-04-15",
                        "renewals": 2})


def test_loan_length_constant_is_fourteen_days():
    assert LOAN_DAYS == 14


# --------------------------------------------------------------------------- #
# Catalogue: books
# --------------------------------------------------------------------------- #
def test_add_and_get(catalog):
    assert catalog.get(ISBN).title == "Clean Code"


def test_add_refuses_a_duplicate_isbn(catalog):
    with pytest.raises(LibraryError, match="already catalogued"):
        catalog.add(book())


def test_add_refuses_a_book_that_starts_part_loaned(catalog):
    with pytest.raises(LibraryError, match="every copy available"):
        catalog.add(book(isbn="X", total=2, available=1))


def test_add_new_parses_the_price(catalog):
    assert catalog.get(ISBN).price_cents == 4250


def test_add_new_refuses_a_bad_price(catalog):
    with pytest.raises(LibraryError):
        catalog.add_new("X", "T", "A", "1.234")


def test_get_refuses_an_unknown_isbn(catalog):
    with pytest.raises(LibraryError, match="not catalogued"):
        catalog.get("000")


def test_get_refuses_a_blank_isbn(catalog):
    with pytest.raises(LibraryError, match="must not be empty"):
        catalog.get("  ")


def test_remove_deletes_a_quiet_book(catalog):
    removed = catalog.remove("978-0134757599")
    assert removed.title == "Refactoring"
    assert "978-0134757599" not in catalog.books


def test_remove_refuses_a_book_on_loan(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    with pytest.raises(LibraryError, match="still on loan"):
        catalog.remove(ISBN)


def test_search_by_title_is_case_insensitive(catalog):
    assert [item.isbn for item in catalog.search("CLEAN")] == [ISBN]


def test_search_by_author(catalog):
    assert [item.isbn for item in catalog.search("fowler")] == \
        ["978-0134757599"]


def test_search_by_isbn(catalog):
    assert [item.isbn for item in catalog.search("4757")] == \
        ["978-0134757599"]


def test_search_with_no_match_is_empty(catalog):
    assert catalog.search("zzz") == []


def test_search_refuses_a_blank_term(catalog):
    with pytest.raises(LibraryError, match="must not be empty"):
        catalog.search("  ")


# --------------------------------------------------------------------------- #
# Catalogue: loans
# --------------------------------------------------------------------------- #
def test_borrow_sets_a_fourteen_day_due_date(catalog):
    loan = catalog.borrow(ISBN, "asha", "2024-04-01")
    assert loan.due_on == DAY(2024, 4, 15)


def test_borrow_decrements_the_available_count(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    assert catalog.get(ISBN).copies_available == 1


def test_borrow_refuses_when_no_copy_is_available(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.borrow(ISBN, "ravi", "2024-04-01")
    with pytest.raises(LibraryError, match="no copy"):
        catalog.borrow(ISBN, "mei", "2024-04-01")


def test_borrow_refuses_the_same_member_twice(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    with pytest.raises(LibraryError, match="already has a copy"):
        catalog.borrow(ISBN, "asha", "2024-04-02")


def test_borrow_refuses_an_unknown_isbn(catalog):
    with pytest.raises(LibraryError, match="not catalogued"):
        catalog.borrow("000", "asha", "2024-04-01")


def test_borrow_refuses_a_blank_member(catalog):
    with pytest.raises(LibraryError, match="member must not be empty"):
        catalog.borrow(ISBN, "  ", "2024-04-01")


def test_borrow_allows_a_member_to_hold_two_different_books(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.borrow("978-0134757599", "asha", "2024-04-01")
    assert len(catalog.member_loans("asha")) == 2


def test_give_back_restores_the_copy(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.give_back(ISBN, "asha", "2024-04-10")
    assert catalog.get(ISBN).copies_available == 2


def test_give_back_marks_the_loan_returned(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    returned, _ = catalog.give_back(ISBN, "asha", "2024-04-10")
    assert returned.returned_on == DAY(2024, 4, 10)
    assert returned.open is False


def test_give_back_on_time_charges_nothing(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    _, fine = catalog.give_back(ISBN, "asha", "2024-04-15")
    assert fine == 0


def test_give_back_late_charges_per_day(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    _, fine = catalog.give_back(ISBN, "asha", "2024-04-20")
    assert fine == 5 * FINE_PER_DAY_CENTS


def test_give_back_refuses_a_second_return(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.give_back(ISBN, "asha", "2024-04-10")
    with pytest.raises(LibraryError, match="no open loan"):
        catalog.give_back(ISBN, "asha", "2024-04-11")


def test_give_back_refuses_the_wrong_member(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    with pytest.raises(LibraryError, match="no open loan"):
        catalog.give_back(ISBN, "ravi", "2024-04-10")


def test_give_back_refuses_a_date_before_the_borrow(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-10")
    with pytest.raises(LibraryError, match="before it was borrowed"):
        catalog.give_back(ISBN, "asha", "2024-04-09")


def test_open_loans_can_be_filtered_by_isbn(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.borrow("978-0134757599", "ravi", "2024-04-01")
    assert len(catalog.open_loans()) == 2
    assert len(catalog.open_loans(ISBN)) == 1


def test_open_loans_exclude_returned_ones(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.give_back(ISBN, "asha", "2024-04-02")
    assert catalog.open_loans() == []


def test_overdue_excludes_the_due_date_itself(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    assert catalog.overdue("2024-04-15") == []
    assert len(catalog.overdue("2024-04-16")) == 1


def test_overdue_is_sorted_by_due_date(catalog):
    catalog.borrow(ISBN, "asha", "2024-03-01")
    catalog.borrow("978-0134757599", "ravi", "2024-02-01")
    assert [loan.member for loan in catalog.overdue("2024-04-01")] == \
        ["ravi", "asha"]


def test_fines_outstanding_sums_open_loans(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    assert catalog.fines_outstanding("2024-04-21") == 6 * FINE_PER_DAY_CENTS


def test_fines_outstanding_ignores_returned_loans(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.give_back(ISBN, "asha", "2024-04-02")
    assert catalog.fines_outstanding("2024-05-01") == 0


def test_member_loans_includes_returned_ones(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.give_back(ISBN, "asha", "2024-04-02")
    assert len(catalog.member_loans("asha")) == 1


def test_member_loans_refuses_a_blank_member(catalog):
    with pytest.raises(LibraryError, match="must not be empty"):
        catalog.member_loans(" ")


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def test_audit_of_a_consistent_catalogue_is_empty(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    assert catalog.audit() == []


def test_audit_catches_a_claimed_unavailable_copy(catalog):
    catalog.books[ISBN] = book(available=0)
    assert "marked on loan" in catalog.audit()[0]


def test_audit_catches_a_loan_of_an_unknown_isbn(catalog):
    catalog.loans.append(Loan("000", "asha", "2024-04-01", "2024-04-15"))
    assert "unknown isbn" in catalog.audit()[0]


def test_audit_of_a_returned_loan_is_clean(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.give_back(ISBN, "asha", "2024-04-02")
    assert catalog.audit() == []


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def test_save_and_load_round_trip(tmp_path, catalog):
    path = tmp_path / "c.json"
    catalog.save(path)
    assert load(path).to_dict() == catalog.to_dict()


def test_save_is_byte_identical_on_a_second_write(tmp_path, catalog):
    path = tmp_path / "c.json"
    catalog.save(path)
    first = path.read_bytes()
    catalog.save(path)
    assert path.read_bytes() == first


def test_save_leaves_no_temporary_file(tmp_path, catalog):
    catalog.save(tmp_path / "c.json")
    assert [item.name for item in tmp_path.iterdir()] == ["c.json"]


def test_save_creates_missing_directories(tmp_path, catalog):
    path = tmp_path / "a" / "b" / "c.json"
    catalog.save(path)
    assert path.is_file()


def test_save_writes_sorted_books(tmp_path, catalog):
    path = tmp_path / "c.json"
    catalog.save(path)
    isbns = [item["isbn"] for item in
             json.loads(path.read_text(encoding="utf-8"))["books"]]
    assert isbns == sorted(isbns)


def test_load_refuses_a_missing_file(tmp_path):
    with pytest.raises(LibraryError, match="not found"):
        load(tmp_path / "nope.json")


def test_load_refuses_invalid_json(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(LibraryError, match="not valid JSON"):
        load(path)


def test_load_refuses_a_missing_section(tmp_path):
    path = tmp_path / "c.json"
    path.write_text('{"books": []}', encoding="utf-8")
    with pytest.raises(LibraryError, match="missing loans"):
        load(path)


def test_load_refuses_a_duplicate_isbn(tmp_path):
    path = tmp_path / "c.json"
    entry = {"isbn": "X", "title": "T", "author": "A", "price_cents": 1,
             "copies_total": 1, "copies_available": 1}
    path.write_text(json.dumps({"books": [entry, entry], "loans": []}),
                    encoding="utf-8")
    with pytest.raises(LibraryError, match="appears twice"):
        load(path)


def test_load_refuses_an_impossible_copy_count(tmp_path):
    path = tmp_path / "c.json"
    entry = {"isbn": "X", "title": "T", "author": "A", "price_cents": 1,
             "copies_total": 1, "copies_available": 2}
    path.write_text(json.dumps({"books": [entry], "loans": []}),
                    encoding="utf-8")
    with pytest.raises(LibraryError, match="outside"):
        load(path)


def test_load_refuses_a_non_object(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(LibraryError, match="JSON object"):
        load(path)


# --------------------------------------------------------------------------- #
# Bundled catalogue and reporting
# --------------------------------------------------------------------------- #
def test_bundled_catalogue_has_six_books():
    assert len(load(DATA_FILE).books) == 6


def test_bundled_catalogue_audits_clean():
    assert load(DATA_FILE).audit() == []


def test_bundled_stats():
    assert stats(load(DATA_FILE)) == {"books": 6, "copies": 8, "available": 5,
                                      "on_loan": 3, "members": 4, "overdue": 2,
                                      "fines_cents": 1075}


def test_bundled_overdue_members():
    assert [loan.member for loan in load(DATA_FILE).overdue()] == \
        ["mei", "asha"]


def test_bundled_loan_due_today_is_not_overdue():
    loans = load(DATA_FILE).open_loans()
    assert any(loan.due_on == AS_OF for loan in loans)


def test_bundled_fines_match_the_per_day_rule():
    catalog = load(DATA_FILE)
    assert catalog.fines_outstanding() == 1075
    for loan in catalog.open_loans():
        assert loan.fine_cents(AS_OF) == min(
            loan.days_late(AS_OF) * FINE_PER_DAY_CENTS, FINE_CAP_CENTS)


def test_bundled_data_file_is_named_catalog_json():
    assert DATA_FILE.name == "catalog.json"


def test_stats_of_an_empty_catalogue():
    assert stats(Catalog()) == {"books": 0, "copies": 0, "available": 0,
                                "on_loan": 0, "members": 0, "overdue": 0,
                                "fines_cents": 0}


def test_render_book_shows_the_price_and_copies(catalog):
    text = render_book(catalog.get(ISBN))
    assert "42.50" in text and "2/2" in text and "Clean Code" in text


def test_render_loan_of_an_open_loan(catalog):
    text = render_loan(catalog.borrow(ISBN, "asha", "2024-04-01"))
    assert "due 2024-04-15" in text


def test_render_loan_of_a_returned_loan(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    text = render_loan(catalog.give_back(ISBN, "asha", "2024-04-10")[0])
    assert "back 2024-04-10" in text


def test_render_loan_shows_a_fine(catalog):
    catalog.borrow(ISBN, "asha", "2024-04-01")
    text = render_loan(catalog.loans[0], DAY(2024, 4, 20))
    assert "fine 1.25" in text


# --------------------------------------------------------------------------- #
# Demo and CLI
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


def test_demo_names_the_float_mangling(capsys):
    run_demo()
    assert "19.989999771118164" in capsys.readouterr().out


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_bundled_books(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "Clean Code" in out
    assert "6 book(s)" in out


def test_cli_stats(capsys):
    assert cli.main(["--stats"]) == 0
    out = capsys.readouterr().out
    assert "3 on loan" in out
    assert "10.75" in out


def test_cli_search(capsys):
    assert cli.main(["--search", "clean"]) == 0
    assert "Clean Code" in capsys.readouterr().out


def test_cli_search_with_no_matches(capsys):
    assert cli.main(["--search", "zzz"]) == 0
    assert "(no books)" in capsys.readouterr().out


def test_cli_overdue(capsys):
    assert cli.main(["--overdue"]) == 0
    out = capsys.readouterr().out
    assert "mei" in out and "asha" in out
    assert "10.75" in out


def test_cli_loans_for_a_member(capsys):
    assert cli.main(["--loans", "asha"]) == 0
    assert "asha" in capsys.readouterr().out


def test_cli_borrow_needs_no_write_to_leave_the_file_alone(tmp_path, capsys):
    path = tmp_path / "c.json"
    catalog = Catalog()
    catalog.add_new(ISBN, "Clean Code", "Robert C. Martin", "42.50", 2)
    catalog.save(path)
    before = path.read_bytes()
    assert cli.main(["--file", str(path), "--borrow", f"{ISBN}:asha"]) == 0
    capsys.readouterr()
    assert path.read_bytes() == before


def test_cli_borrow_with_write_saves(tmp_path, capsys):
    path = tmp_path / "c.json"
    catalog = Catalog()
    catalog.add_new(ISBN, "Clean Code", "Robert C. Martin", "42.50", 2)
    catalog.save(path)
    assert cli.main(["--file", str(path), "--borrow", f"{ISBN}:asha",
                     "--today", "2024-04-01", "--write"]) == 0
    capsys.readouterr()
    reloaded = load(path)
    assert len(reloaded.open_loans()) == 1
    assert reloaded.open_loans()[0].due_on == DAY(2024, 4, 15)


def test_cli_return_prints_the_fine(tmp_path, capsys):
    path = tmp_path / "c.json"
    catalog = Catalog()
    catalog.add_new(ISBN, "Clean Code", "Robert C. Martin", "42.50", 1)
    catalog.borrow(ISBN, "asha", "2024-04-01")
    catalog.save(path)
    assert cli.main(["--file", str(path), "--return", f"{ISBN}:asha",
                     "--today", "2024-04-20", "--write"]) == 0
    out = capsys.readouterr().out
    assert "1.25" in out


def test_cli_borrow_refuses_a_malformed_argument(capsys):
    assert cli.main(["--borrow", "no-colon"]) == 2
    assert "expected ISBN:MEMBER" in capsys.readouterr().err


def test_cli_borrow_of_an_empty_shelf_exits_two(capsys):
    assert cli.main(["--borrow", "978-0262033848:mei"]) == 2
    assert "no copy" in capsys.readouterr().err


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.json"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "19.989999771118164" in out
    assert "utf-8" in out
    assert "2 chunks" in out


def test_cli_json_list(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "list"
    assert len(payload["books"]) == 6
    assert payload["stats"]["fines_cents"] == 1075


def test_cli_json_stats(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--stats", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["stats"]["overdue"] == 2


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--stats", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
