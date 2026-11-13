"""Tests for Contact_Book: validation, repository, search, merge, persistence."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import contacts                                          # noqa: E402
import main as cli                                       # noqa: E402
from contacts import (                                   # noqa: E402
    ContactBook,
    Contact,
    ContactError,
    ConflictError,
    NotFoundError,
    clean_email,
    clean_phone,
    clean_tags,
    run_demo,
    seed_book,
)


def card(**overrides) -> dict:
    payload = {"id": "T-1", "name": "Test Person",
               "email": "test@example.com", "phone": "912345678",
               "company": "Acme", "tags": ["work"]}
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Contact validation
# --------------------------------------------------------------------------- #
def test_contact_normalises_whitespace_and_case():
    contact = Contact.from_dict(card(name="  Ana   Silva ", email=" ANA@Example.COM ",
                                    tags=["Work", " VIP "]))
    assert contact.name == "Ana Silva"
    assert contact.email == "ana@example.com"
    assert contact.tags == ("work", "vip")


def test_contact_keeps_company_whitespace_collapsed():
    assert Contact.from_dict(card(company="  Acme   Labs ")).company == "Acme Labs"


def test_contact_defaults_tags_and_company():
    contact = Contact.from_dict({"id": "T-9", "name": "No Tags",
                                 "email": "n@example.com", "phone": "912345678"})
    assert contact.company == ""
    assert contact.tags == ()


@pytest.mark.parametrize("email", [
    "ana@", "@example.com", "ana.example.com", "two@@example.com",
    "spa ce@example.com", "ana@localhost", "ana@.com",
])
def test_clean_email_rejects_bad_addresses(email):
    with pytest.raises(ContactError):
        clean_email(email)


@pytest.mark.parametrize("email", [
    "a@b.co", "first.last+tag@sub.example.org", "ANA@EXAMPLE.COM",
])
def test_clean_email_accepts_good_addresses(email):
    assert clean_email(email) == email.strip().lower()


def test_clean_email_rejects_empty_and_non_text():
    with pytest.raises(ContactError, match="must not be empty"):
        clean_email("   ")
    with pytest.raises(ContactError, match="must be text"):
        clean_email(None)                                 # type: ignore[arg-type]


def test_clean_phone_strips_separators():
    assert clean_phone("+351 912-345 678") == "+351912345678"
    assert clean_phone("(21) 98765-4321") == "21987654321"
    assert clean_phone("912.345.678") == "912345678"


def test_clean_phone_keeps_leading_plus_only():
    assert clean_phone("+++351912345678") == "+351912345678"


@pytest.mark.parametrize("phone", [
    "12345", "123456", "1234567890123456", "abc-def-ghi", "", "   ",
    "9123456$", "-------",
])
def test_clean_phone_rejects_bad_numbers(phone):
    with pytest.raises(ContactError):
        clean_phone(phone)


def test_clean_phone_accepts_bounds():
    assert clean_phone("1234567") == "1234567"
    assert clean_phone("123456789012345") == "123456789012345"


def test_clean_tags_deduplicates_and_lowercases():
    assert clean_tags(["Work", "work", "VIP"]) == ("work", "vip")


def test_clean_tags_rejects_a_bare_string():
    with pytest.raises(ContactError, match="sequence"):
        clean_tags("work")                                # type: ignore[arg-type]


@pytest.mark.parametrize("tags", [[""], ["bad tag"], ["x" * 21], ["ok", "!"], [3]])
def test_clean_tags_rejects_bad_tags(tags):
    with pytest.raises(ContactError):
        clean_tags(tags)                                  # type: ignore[arg-type]


def test_contact_rejects_empty_name():
    with pytest.raises(ContactError, match="name must not be empty"):
        Contact.from_dict(card(name="   "))


def test_contact_rejects_long_name():
    with pytest.raises(ContactError, match="longer than 60"):
        Contact.from_dict(card(name="x" * 61))


def test_contact_rejects_empty_id():
    with pytest.raises(ContactError, match="id must not be empty"):
        Contact.from_dict(card(id="  "))


def test_contact_from_dict_reports_missing_keys():
    with pytest.raises(ContactError, match="missing email"):
        Contact.from_dict({"id": "T-1", "name": "X", "phone": "912345678"})


def test_contact_from_dict_rejects_non_mapping():
    with pytest.raises(ContactError, match="must be a mapping"):
        Contact.from_dict(["not", "a", "dict"])           # type: ignore[arg-type]


def test_contact_accepts_tags_as_a_string():
    contact = Contact.from_dict(card(tags="work, vip; friend"))
    assert contact.tags == ("work", "vip", "friend")


def test_contact_to_dict_round_trips():
    contact = Contact.from_dict(card())
    assert Contact.from_dict(contact.to_dict()) == contact


def test_contact_is_immutable():
    contact = Contact.from_dict(card())
    with pytest.raises(Exception):
        contact.name = "Other"                            # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Repository
# --------------------------------------------------------------------------- #
def test_seed_book_has_six_contacts():
    book = seed_book()
    assert len(book) == 6
    assert [c.id for c in book] == ["C-006", "C-001", "C-002", "C-003",
                                    "C-004", "C-005"]


def test_empty_book_next_id():
    assert ContactBook().next_id() == "C-001"


def test_create_uses_sequential_ids():
    book = ContactBook()
    first = book.create("A One", "a@example.com", "912345678")
    second = book.create("B Two", "b@example.com", "912345679")
    assert (first.id, second.id) == ("C-001", "C-002")
    assert book.next_id() == "C-003"


def test_seed_book_next_id_continues():
    assert seed_book().next_id() == "C-007"


def test_get_missing_id_raises():
    with pytest.raises(NotFoundError, match="no contact with id"):
        seed_book().get("C-999")


def test_by_email_finds_and_normalises():
    book = seed_book()
    assert book.by_email(" ANA.SILVA@example.com ").id == "C-001"


def test_by_email_missing_raises():
    with pytest.raises(NotFoundError, match="no contact with email"):
        seed_book().by_email("nobody@example.com")


def test_add_duplicate_email_conflicts():
    book = seed_book()
    with pytest.raises(ConflictError, match="already used by C-001"):
        book.create("Copy", "ana.silva@example.com", "912345680")


def test_add_duplicate_id_conflicts():
    book = seed_book()
    with pytest.raises(ConflictError, match="already exists"):
        book.add(Contact.from_dict(card(id="C-002", email="fresh@example.com")))


def test_add_accepts_a_dict():
    book = ContactBook()
    assert book.add(card()).id == "T-1"


def test_update_changes_a_field():
    book = seed_book()
    updated = book.update("C-004", company="Acme Labs")
    assert updated.company == "Acme Labs"
    assert book.get("C-004").company == "Acme Labs"


def test_update_revalidates_and_leaves_record_untouched():
    book = seed_book()
    with pytest.raises(ContactError, match="not a valid address"):
        book.update("C-002", email="broken@")
    assert book.get("C-002").email == "bruno@example.com"


def test_update_rejects_unknown_field():
    with pytest.raises(ContactError, match="unknown field"):
        seed_book().update("C-002", nickname="Bruno")


def test_update_rejects_empty_change():
    with pytest.raises(ContactError, match="no fields to update"):
        seed_book().update("C-002")


def test_update_rejects_changing_the_id():
    with pytest.raises(ContactError, match="id cannot be changed"):
        seed_book().update("C-002", id="C-100")


def test_update_email_updates_the_index():
    book = seed_book()
    book.update("C-002", email="bruno.costa@example.com")
    assert book.by_email("bruno.costa@example.com").id == "C-002"
    with pytest.raises(NotFoundError):
        book.by_email("bruno@example.com")


def test_update_email_to_owned_address_conflicts():
    with pytest.raises(ConflictError, match="already used by C-001"):
        seed_book().update("C-002", email="ana.silva@example.com")


def test_update_tags_accepts_a_list():
    book = seed_book()
    assert book.update("C-002", tags=["work", "vip"]).tags == ("work", "vip")


def test_remove_returns_the_record_and_forgets_it():
    book = seed_book()
    removed = book.remove("C-005")
    assert removed.name == "Elena Rossi"
    assert "C-005" not in book
    assert len(book) == 5
    book.add(removed)                      # the email is free again
    assert "C-005" in book


def test_remove_missing_raises():
    with pytest.raises(NotFoundError):
        seed_book().remove("C-404")


def test_clear_empties_the_book():
    book = seed_book()
    book.clear()
    assert len(book) == 0
    assert book.next_id() == "C-001"


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def test_search_by_name_is_case_insensitive():
    assert [c.id for c in seed_book().search("ANA")] == ["C-006", "C-001"]


def test_search_requires_every_term():
    assert [c.id for c in seed_book().search("ana lisbon")] == ["C-001"]
    assert seed_book().search("ana nowhere") == []


def test_search_matches_email_and_company():
    book = seed_book()
    assert [c.id for c in book.search("@example.org")] == ["C-003"]
    assert [c.id for c in book.search("northwind")] == \
        ["C-006", "C-001", "C-002"]


def test_search_by_tag():
    book = seed_book()
    assert [c.id for c in book.search(tag="work")] == ["C-006", "C-002", "C-003"]
    assert [c.id for c in book.search(tag="vip")] == ["C-003"]


def test_search_by_tag_with_query():
    assert [c.id for c in seed_book().search("ana", tag="work")] == ["C-006"]


def test_search_by_company():
    assert {c.id for c in seed_book().search(company="acme")} == \
        {"C-003", "C-004"}


def test_search_empty_query_returns_sorted_everything():
    book = seed_book()
    assert book.search() == book.all()


def test_search_no_hits():
    assert seed_book().search("nobody") == []


def test_search_rejects_non_text_query():
    with pytest.raises(ContactError, match="query must be text"):
        seed_book().search(42)                            # type: ignore[arg-type]


def test_all_is_sorted_by_name_then_email():
    names = [c.name for c in seed_book().all()]
    assert names == sorted(names, key=str.casefold)


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
def _incoming():
    return ContactBook([
        Contact.from_dict(card(id="X-1", name="Ana Silva",
                               email="ana.silva@example.com",
                               phone="+351999999999", company="Elsewhere",
                               tags=["new"])),
        Contact.from_dict(card(id="X-2", name="Gita Patel",
                               email="gita@example.com",
                               phone="+44 20 7946 0000", tags=["vendor"])),
    ])


def test_merge_prefer_existing_keeps_mine():
    book = seed_book()
    report = book.merge(_incoming(), policy="prefer-existing")
    assert report == {"added": 1, "updated": 0, "unchanged": 1, "skipped": 0}
    assert book.get("C-001").company == "Northwind"
    assert len(book) == 7


def test_merge_prefer_incoming_takes_theirs():
    book = seed_book()
    report = book.merge(_incoming(), policy="prefer-incoming")
    assert report["updated"] == 1 and report["added"] == 1
    merged = book.get("C-001")
    assert merged.company == "Elsewhere"
    assert merged.phone == "+351999999999"
    assert merged.tags == ("friend", "lisbon", "new")


def test_merge_keeps_existing_values_when_incoming_is_empty():
    book = seed_book()
    empty = ContactBook([Contact(id="Z-1", name="Ana Silva",
                                 email="ana.silva@example.com",
                                 phone="912345678")])
    book.merge(empty, policy="prefer-incoming")
    merged = book.get("C-001")
    assert merged.company == "Northwind"        # incoming had none
    assert merged.tags == ("friend", "lisbon")  # union with nothing


def test_merge_unknown_policy_changes_nothing():
    book = seed_book()
    with pytest.raises(ContactError, match="unknown merge policy"):
        book.merge(_incoming(), policy="newest")
    assert len(book) == 6


def test_merge_reports_unchanged_when_identical():
    book = seed_book()
    twin = ContactBook([book.get("C-002")])
    assert book.merge(twin, policy="prefer-incoming")["unchanged"] == 1


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def test_json_round_trip(tmp_path):
    book = seed_book()
    path = book.save(tmp_path / "c.json")
    again = ContactBook.load(path)
    assert again.all() == book.all()
    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "C-006"


def test_load_missing_file(tmp_path):
    with pytest.raises(ContactError, match="file not found"):
        ContactBook.load(tmp_path / "nope.json")


def test_load_rejects_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContactError, match="not valid JSON"):
        ContactBook.load(path)


def test_load_rejects_non_list(tmp_path):
    path = tmp_path / "obj.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    with pytest.raises(ContactError, match="list of contacts"):
        ContactBook.load(path)


def test_load_reports_the_index_of_a_bad_contact(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([card(), card(email="broken@")]),
                    encoding="utf-8")
    with pytest.raises(ContactError, match="contact 1:"):
        ContactBook.load(path)


def test_csv_export_and_import(tmp_path):
    book = seed_book()
    path = book.export_csv(tmp_path / "c.csv")
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 6
    assert rows[0]["tags"] == "friend;work"
    assert ContactBook.from_csv(path).all() == book.all()


def test_csv_missing_column_is_reported(tmp_path):
    path = tmp_path / "c.csv"
    path.write_text("id,name,email\nC-1,X,x@example.com\n", encoding="utf-8")
    with pytest.raises(ContactError, match="missing column"):
        ContactBook.from_csv(path)


def test_csv_bad_row_is_reported(tmp_path):
    path = tmp_path / "c.csv"
    path.write_text(
        "id,name,email,phone,company,tags\nC-1,X,x@example.com,12,\n",
        encoding="utf-8")
    with pytest.raises(ContactError, match="row 1:"):
        ContactBook.from_csv(path)


# --------------------------------------------------------------------------- #
# Data file and demo
# --------------------------------------------------------------------------- #
def test_bundled_data_file_loads():
    book = ContactBook.load(PROJECT / "data" / "contacts.json")
    assert len(book) == 6
    assert book.get("C-003").phone == "21987654321"


def test_demo_returns_zero_and_prints(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


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


def test_cli_lists_everything(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "6 of 6 contacts" in out


def test_cli_search(capsys):
    assert cli.main(["--search", "ana"]) == 0
    out = capsys.readouterr().out
    assert "2 of 6 contacts" in out
    assert "C-006" in out and "C-001" in out


def test_cli_search_with_tag(capsys):
    assert cli.main(["--search", "ana", "--tag", "work"]) == 0
    assert "1 of 6 contacts" in capsys.readouterr().out


def test_cli_add(capsys):
    assert cli.main(["--add", "Gita Patel|gita@example.com|+44 20 7946 0000"]) == 0
    out = capsys.readouterr().out
    assert "Added C-007" in out


def test_cli_add_rejects_bad_spec(capsys):
    assert cli.main(["--add", "only-name"]) == 2
    assert "NAME|EMAIL|PHONE" in capsys.readouterr().err


def test_cli_add_rejects_invalid_contact(capsys):
    assert cli.main(["--add", "X|bad@|912345678"]) == 2
    assert "not a valid address" in capsys.readouterr().err


def test_cli_export_csv(tmp_path, capsys):
    target = tmp_path / "out.csv"
    assert cli.main(["--export-csv", str(target)]) == 0
    capsys.readouterr()
    assert len(target.read_text(encoding="utf-8").splitlines()) == 7


def test_cli_save_and_json(tmp_path, capsys):
    saved = tmp_path / "saved.json"
    listed = tmp_path / "listed.json"
    assert cli.main(["--save", str(saved), "--json", str(listed)]) == 0
    capsys.readouterr()
    assert len(json.loads(saved.read_text(encoding="utf-8"))) == 6
    assert len(json.loads(listed.read_text(encoding="utf-8"))) == 6


def test_cli_merge(tmp_path, capsys):
    other = tmp_path / "other.json"
    other.write_text(json.dumps([card(id="Z-1", email="zed@example.com")]),
                     encoding="utf-8")
    assert cli.main(["--merge", str(other)]) == 0
    out = capsys.readouterr().out
    assert "'added': 1" in out
    assert "7 of 7 contacts" in out


def test_cli_merge_unknown_policy_rejected_by_argparse(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--policy", "newest"])
    assert excinfo.value.code == 2


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.json"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--search", "ana", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_parse_add_helper():
    assert cli.parse_add("A|a@example.com|912345678") == \
        ["A", "a@example.com", "912345678"]
