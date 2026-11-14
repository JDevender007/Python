"""Tests for Data_Cleaning: the legacy bugs, text cleaning, sniffing, tables."""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import cleaning                                          # noqa: E402
import main as cli                                       # noqa: E402
from cleaning import (                                   # noqa: E402
    BLANKS,
    CleanError,
    broken_clean,
    clean_header,
    clean_row,
    clean_table,
    clean_text,
    collapse_spaces,
    dedupe,
    legacy_clean,
    load_lines,
    load_messy,
    normalise,
    run_demo,
    sniff,
    strip_symbols,
    tokens,
)

LEGACY_SCAN = cleaning.LEGACY_SCAN


# --------------------------------------------------------------------------- #
# The legacy loop
# --------------------------------------------------------------------------- #
def test_legacy_clean_returns_the_input_unchanged():
    assert legacy_clean(LEGACY_SCAN) == LEGACY_SCAN


def test_legacy_clean_keeps_punctuation():
    cleaned = legacy_clean("a+b#c{d}e\\f")
    assert cleaned == "a+b#c{d}e\\f"


def test_legacy_clean_keeps_digits():
    assert legacy_clean("order9") == "order9"


def test_legacy_clean_of_empty_is_empty():
    assert legacy_clean("") == ""


def test_legacy_clean_of_letters_only():
    assert legacy_clean("abc def") == "abc def"


def test_legacy_clean_rejects_non_text():
    with pytest.raises(CleanError, match="must be a string"):
        legacy_clean(None)


def test_isalpha_without_parentheses_is_truthy():
    assert bool("+".isalpha) is True
    assert bool(" ".isalpha) is True


def test_the_else_branch_is_unreachable_in_the_legacy_loop():
    # every character satisfies the condition, so `clean + 1` never runs
    assert all(bool(ch.isalpha) or ch.isspace() for ch in LEGACY_SCAN)


# --------------------------------------------------------------------------- #
# The half-fixed loop
# --------------------------------------------------------------------------- #
def test_broken_clean_crashes_on_punctuation():
    with pytest.raises(TypeError):
        broken_clean("a+b")


def test_broken_clean_crashes_on_a_digit():
    with pytest.raises(TypeError):
        broken_clean("a1")


def test_broken_clean_crashes_on_the_legacy_scan():
    with pytest.raises(TypeError):
        broken_clean(LEGACY_SCAN)


def test_broken_clean_works_on_letters_and_spaces():
    assert broken_clean("abc def") == "abc def"


def test_broken_clean_of_empty_is_empty():
    assert broken_clean("") == ""


def test_broken_clean_rejects_non_text():
    with pytest.raises(CleanError, match="must be a string"):
        broken_clean(42)


# --------------------------------------------------------------------------- #
# Symbol stripping
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw, expected", [
    ("a+b", "ab"),
    ("a#b", "ab"),
    ("a{b}c", "abc"),
    ("a\\b", "ab"),
    ("a-b", "ab"),
    ("a.b,c;d:e", "abcde"),
    ("100%", "100"),
    ("a  b", "a  b"),
])
def test_strip_symbols_removes_punctuation(raw, expected):
    assert strip_symbols(raw) == expected


def test_strip_symbols_keeps_letters_and_digits():
    assert strip_symbols("abc123") == "abc123"


def test_strip_symbols_keeps_whitespace():
    assert strip_symbols("a\tb\nc") == "a\tb\nc"


def test_strip_symbols_keeps_non_ascii_letters():
    assert strip_symbols("caf\u00e9") == "caf\u00e9"


def test_strip_symbols_of_empty_is_empty():
    assert strip_symbols("") == ""


def test_strip_symbols_of_symbols_only_is_empty():
    assert strip_symbols("+-#{}[]") == ""


def test_strip_symbols_rejects_non_text():
    with pytest.raises(CleanError, match="must be a string"):
        strip_symbols(None)


def test_strip_symbols_is_idempotent():
    once = strip_symbols(LEGACY_SCAN)
    assert strip_symbols(once) == once


# --------------------------------------------------------------------------- #
# Whitespace
# --------------------------------------------------------------------------- #
def test_collapse_spaces_trims_and_squeezes():
    assert collapse_spaces("  a   b  ") == "a b"


def test_collapse_spaces_handles_tabs_and_newlines():
    assert collapse_spaces("a\t\tb\n\nc") == "a b c"


def test_collapse_spaces_of_whitespace_only_is_empty():
    assert collapse_spaces("   \t\n ") == ""


def test_collapse_spaces_of_empty_is_empty():
    assert collapse_spaces("") == ""


def test_collapse_spaces_rejects_non_text():
    with pytest.raises(CleanError, match="must be a string"):
        collapse_spaces(1.5)


# --------------------------------------------------------------------------- #
# Whole-text helpers
# --------------------------------------------------------------------------- #
def test_clean_text_strips_and_collapses():
    assert clean_text("  Hello,   WORLD!  ") == "Hello WORLD"


def test_clean_text_preserves_case():
    assert clean_text("Hello") == "Hello"


def test_clean_text_of_the_legacy_scan():
    assert clean_text(LEGACY_SCAN) == (
        "Thesenotesreveal9Newton seekingout anunderlying structure "
        "tothepyramid")


def test_clean_text_removes_plus_and_backslash():
    cleaned = clean_text(LEGACY_SCAN)
    assert "+" not in cleaned and "\\" not in cleaned and "{" not in cleaned


def test_clean_text_keeps_the_digit():
    assert "9" in clean_text(LEGACY_SCAN)


def test_clean_text_is_idempotent():
    once = clean_text(LEGACY_SCAN)
    assert clean_text(once) == once


def test_normalise_casefolds():
    assert normalise("  Hello WORLD ") == "hello world"


def test_normalise_equals_clean_text_for_lower_input():
    assert normalise("abc") == clean_text("abc")


def test_tokens_splits_on_whitespace():
    assert tokens("  one   two  three ") == ["one", "two", "three"]


def test_tokens_drops_punctuation():
    assert tokens("Hello, WORLD!") == ["hello", "world"]


def test_tokens_of_punctuation_only_is_empty():
    assert tokens("!!!") == []


def test_tokens_of_empty_is_empty():
    assert tokens("") == []


# --------------------------------------------------------------------------- #
# Dedupe
# --------------------------------------------------------------------------- #
def test_dedupe_keeps_the_first_spelling():
    assert dedupe(["Alpha", "alpha"]) == ["Alpha"]


def test_dedupe_preserves_order():
    assert dedupe(["c", "a", "c", "b"]) == ["c", "a", "b"]


def test_dedupe_of_numbers():
    assert dedupe([1, 2, 1, 3]) == [1, 2, 3]


def test_dedupe_of_empty_is_empty():
    assert dedupe([]) == []


def test_dedupe_with_a_key():
    assert dedupe(["a", "A", "b"], key=str.upper) == ["a", "b"]


# --------------------------------------------------------------------------- #
# Sniffing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw, expected", [
    ("42", 42),
    ("0", 0),
    ("-7", -7),
    ("+11", 11),
    (" 42 ", 42),
    ("3.5", 3.5),
    ("-0.25", -0.25),
    ("2024-01-31", datetime.date(2024, 1, 31)),
    ("yes", True),
    ("no", False),
    ("TRUE", True),
    ("N", False),
])
def test_sniff_infers_the_type(raw, expected):
    result = sniff(raw)
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize("raw", ["", "  ", "n/a", "NULL", "none", "-", "--"])
def test_sniff_maps_blanks_to_none(raw):
    assert sniff(raw) is None


@pytest.mark.parametrize("raw", ["007", "00", "not-a-date", "Alice", "1e5",
                                 "12.34.56", "2024-13-01", "1_000"])
def test_sniff_leaves_ambiguous_cells_as_text(raw):
    assert sniff(raw) == raw


def test_sniff_keeps_a_leading_zero_as_text():
    assert isinstance(sniff("007"), str)


def test_sniff_of_none_is_none():
    assert sniff(None) is None


def test_sniff_passes_non_text_through():
    assert sniff(7) == 7
    assert sniff(1.5) == 1.5
    assert sniff(True) is True


def test_sniff_rejects_an_impossible_date_as_text():
    assert sniff("2024-02-31") == "2024-02-31"


def test_blanks_list_is_lowercase_for_comparison():
    assert all(word == word.casefold() for word in BLANKS)


# --------------------------------------------------------------------------- #
# Headers and rows
# --------------------------------------------------------------------------- #
def test_clean_header_normalises_names():
    assert clean_header({" city ": "x", "Joined On": "y"}) == \
        {"city": "x", "joined_on": "y"}


def test_clean_header_lowercases():
    assert list(clean_header({"ID": 1})) == ["id"]


def test_clean_header_rejects_a_collision():
    with pytest.raises(CleanError, match="duplicate header"):
        clean_header({"City": 1, "city": 2})


def test_clean_header_rejects_an_empty_name():
    with pytest.raises(CleanError, match="empty name"):
        clean_header({"!!!": 1})


def test_clean_row_sniffs_every_value():
    row = clean_row({"id": "1", "name": " Alice ", "active": "yes"})
    assert row == {"id": 1, "name": "Alice", "active": True}


def test_clean_row_rejects_non_dict():
    with pytest.raises(CleanError, match="must be a dict"):
        clean_row(["id", 1])


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def test_clean_table_sniffs_and_reports():
    rows = [{"id": "1", "name": " Alice ", "active": "yes"}]
    cleaned, report = clean_table(rows)
    assert cleaned == [{"id": 1, "name": "Alice", "active": True}]
    assert report["rows_in"] == 1 and report["rows_out"] == 1
    assert report["to_int"] == 1 and report["to_bool"] == 1


def test_clean_table_drops_exact_duplicates():
    rows = [{"id": "1"}, {"id": "1"}, {"id": "2"}]
    cleaned, report = clean_table(rows)
    assert len(cleaned) == 2
    assert report["duplicate_rows"] == 1


def test_clean_table_counts_cells_after_dedup():
    rows = [{"id": "1", "b": "x"}, {"id": "1", "b": "x"}]
    _, report = clean_table(rows)
    assert report["cells"] == 2


def test_clean_table_counts_blanks():
    _, report = clean_table([{"a": "", "b": "n/a"}])
    assert report["blanks_to_none"] == 2


def test_clean_table_of_an_empty_list_raises():
    with pytest.raises(CleanError, match="no rows"):
        clean_table([])


def test_clean_table_of_a_non_list_raises():
    with pytest.raises(CleanError, match="must be a list"):
        clean_table("nope")


def test_clean_table_rejects_a_non_dict_row():
    with pytest.raises(CleanError, match="must be a dict"):
        clean_table([["id", "1"]])


def test_clean_table_is_idempotent():
    rows = load_messy()
    cleaned, _ = clean_table(rows)
    again, report = clean_table(cleaned)
    assert again == cleaned
    assert report["duplicate_rows"] == 0


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
def test_scan_file_has_five_lines():
    assert len(load_lines()) == 5


def test_scan_lines_are_distinct_after_cleaning():
    cleaned = [clean_text(line) for line in load_lines()]
    assert dedupe(cleaned) == cleaned


def test_scan_lines_all_have_content():
    assert all(clean_text(line) for line in load_lines())


def test_scan_loader_skips_comments_and_blanks(tmp_path):
    path = tmp_path / "s.txt"
    path.write_text("# comment\n\na+b\n\n", encoding="utf-8")
    assert load_lines(path) == ["a+b"]


def test_scan_loader_of_a_missing_file(tmp_path):
    with pytest.raises(CleanError, match="not found"):
        load_lines(tmp_path / "nope.txt")


def test_scan_loader_of_an_empty_file(tmp_path):
    path = tmp_path / "s.txt"
    path.write_text("# only comments\n\n", encoding="utf-8")
    with pytest.raises(CleanError, match="no lines"):
        load_lines(path)


def test_messy_csv_has_six_rows():
    assert len(load_messy()) == 6


def test_messy_csv_keeps_the_raw_header_names():
    assert list(load_messy()[0]) == ["id", "name", " city ", "amount",
                                     "joined", "active", "note"]


def test_messy_csv_missing_file(tmp_path):
    with pytest.raises(CleanError, match="not found"):
        load_messy(tmp_path / "nope.csv")


def test_messy_csv_rejects_a_short_row(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("a,b\n1,2,3\n", encoding="utf-8")
    with pytest.raises(CleanError, match="line 2"):
        load_messy(path)


def test_messy_csv_needs_a_row(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(CleanError, match="header and at least one row"):
        load_messy(path)


def test_cleaned_csv_has_five_rows():
    cleaned, _ = clean_table(load_messy())
    assert len(cleaned) == 5


def test_cleaned_csv_report():
    _, report = clean_table(load_messy())
    assert report["rows_in"] == 6
    assert report["rows_out"] == 5
    assert report["duplicate_rows"] == 1
    assert report["blanks_to_none"] == 2
    assert report["to_date"] == 4
    assert report["to_bool"] == 4
    assert report["cells"] == 35


def test_cleaned_csv_first_row():
    cleaned, _ = clean_table(load_messy())
    first = cleaned[0]
    assert first["id"] == 1
    assert first["name"] == "Alice"
    assert first["city"] == "Mumbai"
    assert first["amount"] == 42
    assert first["joined"] == datetime.date(2024, 1, 31)
    assert first["active"] is True
    assert first["note"] == "first order"


def test_cleaned_csv_keeps_the_leading_zero():
    cleaned, _ = clean_table(load_messy())
    amounts = [row["amount"] for row in cleaned]
    assert "007" in amounts


def test_cleaned_csv_keeps_an_unparseable_date_as_text():
    cleaned, _ = clean_table(load_messy())
    assert cleaned[-1]["joined"] == "not-a-date"


def test_cleaned_csv_maps_an_empty_note_to_none():
    cleaned, _ = clean_table(load_messy())
    assert cleaned[1]["note"] is None


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


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_table_mode(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "rows_in" in out and "rows_out" in out
    assert "Alice" in out and "Mumbai" in out


def test_cli_table_shows_the_duplicate_count(capsys):
    assert cli.main([]) == 0
    assert "duplicate_rows" in capsys.readouterr().out


def test_cli_scans_mode(capsys):
    assert cli.main(["--scans"]) == 0
    out = capsys.readouterr().out
    assert "5 line(s) cleaned" in out
    assert "Thesenotesreveal9Newton" in out


def test_cli_text_mode(capsys):
    assert cli.main(["--text", "  Hello,   WORLD!  "]) == 0
    out = capsys.readouterr().out
    assert "'Hello WORLD'" in out
    assert "['hello', 'world']" in out


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "unchanged?     True" in out
    assert "TypeError" in out


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_json_table_serialises_dates(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "table"
    assert payload["report"]["rows_out"] == 5
    assert payload["rows"][0]["joined"] == "2024-01-31"


def test_cli_json_text(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--text", "a+b", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["cleaned"] == "ab"
    assert payload["tokens"] == ["ab"]


def test_cli_custom_csv(tmp_path, capsys):
    path = tmp_path / "one.csv"
    path.write_text("a,b\n 1 ,yes\n", encoding="utf-8")
    assert cli.main(["--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "rows_out" in out
    assert "yes" in out


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--scans", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_module_exposes_its_data_paths():
    assert cleaning.SCAN_FILE.name == "scan.txt"
    assert cleaning.MESSY_FILE.name == "messy.csv"
