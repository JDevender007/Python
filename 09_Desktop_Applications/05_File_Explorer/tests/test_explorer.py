"""Tests for the file lab: sort() is not a listing order, a join is not confinement."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import explorer as module                                   # noqa: E402
import main as cli                                          # noqa: E402
from explorer import (                                      # noqa: E402
    FIELD,
    HIDDEN_PREFIX,
    KINDS,
    LEGACY_CONTAINS,
    LEGACY_LISTING,
    UNITS,
    Entry,
    ExplorerError,
    audit,
    confine,
    contains,
    divide_half_up,
    format_size,
    hidden,
    is_confined,
    is_hidden,
    legacy_contains,
    legacy_format_size,
    legacy_join,
    legacy_normalised,
    legacy_sort_entries,
    legacy_sort_names,
    measure,
    natural_key,
    parse_listing,
    problems,
    read_listing,
    run_demo,
    sort_entries,
    sort_names,
    visible,
)

ENTRIES = read_listing()
MEASURED = measure(ENTRIES)


# --------------------------------------------------------------------------- #
# divide_half_up
# --------------------------------------------------------------------------- #
def test_divide_half_up_rounds_a_tie_up():
    assert divide_half_up(5, 2) == 3


def test_divide_half_up_rounds_12_5_up():
    assert divide_half_up(25, 2) == 13


def test_divide_half_up_floors_below_the_tie():
    assert divide_half_up(7, 3) == 2


def test_divide_half_up_of_an_exact_division():
    assert divide_half_up(12, 4) == 3


def test_divide_half_up_rounds_a_negative_tie_away_from_zero():
    assert divide_half_up(-5, 2) == -3


def test_divide_half_up_refuses_a_zero_denominator():
    with pytest.raises(ExplorerError, match="a denominator is positive"):
        divide_half_up(1, 0)


def test_divide_half_up_refuses_a_float_numerator():
    with pytest.raises(ExplorerError, match="a numerator is a whole number"):
        divide_half_up(1.5, 2)


def test_divide_half_up_refuses_a_bool_denominator():
    with pytest.raises(ExplorerError, match="a denominator is a whole number"):
        divide_half_up(1, True)


# --------------------------------------------------------------------------- #
# format_size
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("size,expected", [
    (0, "0 B"), (1, "1 B"), (512, "512 B"), (1023, "1023 B"),
    (1024, "1 KB"), (1280, "1.3 KB"), (1536, "1.5 KB"), (2047, "2 KB"),
    (1048576, "1 MB"), (1572864, "1.5 MB"), (1073741824, "1 GB"),
])
def test_format_size_pins_its_tenths(size, expected):
    assert format_size(size) == expected


def test_format_size_drops_a_zero_tenth():
    assert ".0" not in format_size(1024)


def test_format_size_refuses_a_negative():
    with pytest.raises(ExplorerError, match="not negative"):
        format_size(-1)


def test_format_size_refuses_a_float():
    with pytest.raises(ExplorerError, match="whole number"):
        format_size(1.5)


def test_format_size_refuses_a_bool():
    with pytest.raises(ExplorerError, match="whole number"):
        format_size(True)


def test_the_legacy_formatter_rounds_1280_down():
    assert legacy_format_size(1280) == "1.2 KB"


def test_the_legacy_formatter_gives_a_byte_a_tenth():
    assert legacy_format_size(1) == "1.0 B"


def test_the_legacy_formatter_agrees_on_a_clean_kilobyte():
    assert legacy_format_size(1024) == "1.0 KB"


def test_the_legacy_formatter_falls_off_the_end_of_its_units():
    huge = 1024 ** 5
    assert legacy_format_size(huge).endswith("TB")


def test_the_units_are_the_five_names():
    assert UNITS == ("B", "KB", "MB", "GB", "TB")


# --------------------------------------------------------------------------- #
# natural_key and the two sorts
# --------------------------------------------------------------------------- #
def test_a_digit_run_becomes_a_number():
    assert natural_key("file10.txt") == ((1, "file"), (0, 10), (1, ".txt"))


def test_the_key_is_case_folded():
    assert natural_key("FILE10.TXT") == natural_key("file10.txt")


def test_a_name_without_digits_is_one_text_part():
    assert natural_key("notes") == ((1, "notes"),)


def test_a_leading_digit_comes_first():
    assert natural_key("2 notes")[0] == (0, 2)


def test_leading_zeros_compare_as_the_same_number():
    assert natural_key("file007")[1] == natural_key("file7")[1]


def test_natural_key_refuses_a_blank_name():
    with pytest.raises(ExplorerError, match="not blank"):
        natural_key("   ")


def test_natural_key_refuses_a_number():
    with pytest.raises(ExplorerError, match="a name is text"):
        natural_key(7)


def test_file2_sorts_before_file10():
    assert sort_names(["file10.txt", "file2.txt"]) == ["file2.txt",
                                                       "file10.txt"]


def test_the_legacy_sort_puts_file10_first():
    assert legacy_sort_names(["file10.txt", "file2.txt"]) == ["file10.txt",
                                                              "file2.txt"]


def test_the_two_sorts_disagree_on_digits():
    names = ["file1.txt", "file2.txt", "file10.txt", "file20.txt"]
    assert sort_names(names) != legacy_sort_names(names)


def test_sort_names_folds_case():
    assert sort_names(["Zebra.txt", "apple.txt", "Banana.txt"]) == \
        ["apple.txt", "Banana.txt", "Zebra.txt"]


def test_the_legacy_sort_puts_capitals_first():
    assert legacy_sort_names(["Zebra.txt", "apple.txt"]) == ["Zebra.txt",
                                                             "apple.txt"]


def test_a_casefold_tie_is_broken_by_the_raw_name():
    assert sort_names(["Stra\u00dfe", "STRASSE"]) == ["STRASSE", "Stra\u00dfe"]


def test_a_casefold_tie_is_a_tie_in_the_key():
    assert natural_key("Stra\u00dfe") == natural_key("STRASSE")


def test_sorting_the_same_names_twice_gives_the_same_order():
    names = ["b.txt", "A.txt", "a.txt", "B.txt"]
    assert sort_names(names) == sort_names(list(reversed(names)))


def test_a_sort_is_a_permutation_of_its_input():
    names = [entry.name for entry in ENTRIES]
    assert sorted(sort_names(names)) == sorted(names)


def test_a_sort_keeps_every_duplicate():
    assert len(sort_names(["a", "a", "b"])) == 3


def test_sort_names_accepts_a_generator():
    assert sort_names(name for name in ["b", "a"]) == ["a", "b"]


def test_sort_names_refuses_a_number():
    with pytest.raises(ExplorerError, match="a name is text"):
        sort_names(["a", 7])


def test_sort_names_accepts_an_empty_list():
    assert sort_names([]) == []


def test_is_hidden_reads_a_leading_dot():
    assert is_hidden(".config") is True


def test_a_name_without_a_dot_is_visible():
    assert is_hidden("notes.txt") is False


def test_a_dot_inside_a_name_is_not_hidden():
    assert is_hidden("notes.txt.bak") is False


def test_is_hidden_refuses_a_number():
    with pytest.raises(ExplorerError, match="a name is text"):
        is_hidden(7)


def test_the_hidden_prefix_is_a_dot():
    assert HIDDEN_PREFIX == "."


# --------------------------------------------------------------------------- #
# Entry
# --------------------------------------------------------------------------- #
def test_an_entry_holds_a_name_a_kind_and_a_size():
    entry = Entry("notes.txt", "file", 1023)
    assert (entry.name, entry.kind, entry.size) == ("notes.txt", "file", 1023)


def test_a_directory_entry_is_a_directory():
    assert Entry("docs", "dir", 0).is_dir() is True


def test_a_file_entry_is_not_a_directory():
    assert Entry("notes.txt", "file", 1).is_dir() is False


def test_an_entry_reports_whether_it_is_hidden():
    assert Entry(".config", "file", 12).hidden() is True


def test_an_entry_line_names_the_kind_the_name_and_the_size():
    assert Entry("notes.txt", "file", 1023).line() == "- notes.txt          1023 B"


def test_a_directory_line_starts_with_a_d():
    assert Entry("docs", "dir", 0).line().startswith("d docs")


def test_an_entry_renders_its_size_two_ways():
    entry = Entry("Zebra.txt", "file", 1280)
    assert (entry.shown_size(), entry.legacy_size()) == ("1.3 KB", "1.2 KB")


def test_an_entry_refuses_a_blank_name():
    with pytest.raises(ExplorerError, match="not blank"):
        Entry("  ", "file", 1)


def test_an_entry_refuses_a_name_with_a_slash():
    with pytest.raises(ExplorerError, match="holds no separator"):
        Entry("docs/notes.txt", "file", 1)


def test_an_entry_refuses_a_name_with_a_backslash():
    with pytest.raises(ExplorerError, match="holds no separator"):
        Entry("docs\\notes.txt", "file", 1)


def test_an_entry_refuses_an_unknown_kind():
    with pytest.raises(ExplorerError, match="a kind is"):
        Entry("notes.txt", "link", 1)


def test_an_entry_refuses_a_negative_size():
    with pytest.raises(ExplorerError, match="not negative"):
        Entry("notes.txt", "file", -1)


def test_an_entry_refuses_a_float_size():
    with pytest.raises(ExplorerError, match="whole number"):
        Entry("notes.txt", "file", 1.0)


def test_the_two_kinds_are_named():
    assert KINDS == ("file", "dir")


# --------------------------------------------------------------------------- #
# Sorting a listing
# --------------------------------------------------------------------------- #
def test_sort_entries_puts_directories_first():
    names = [entry.name for entry in sort_entries(ENTRIES)]
    assert names[:2] == ["docs", "pictures"]


def test_sort_entries_is_natural_inside_a_kind():
    names = [entry.name for entry in sort_entries(ENTRIES)]
    assert names.index("file2.txt") < names.index("file10.txt")


def test_sort_entries_is_case_blind():
    names = [entry.name for entry in sort_entries(ENTRIES)]
    assert names.index("apple.txt") < names.index("Zebra.txt")


def test_the_legacy_sort_puts_file10_before_file2():
    names = [entry.name for entry in legacy_sort_entries(ENTRIES)]
    assert names.index("file10.txt") < names.index("file2.txt")


def test_the_legacy_sort_puts_report_10_before_report_9():
    names = [entry.name for entry in legacy_sort_entries(ENTRIES)]
    assert names.index("report-10.txt") < names.index("report-9.txt")


def test_the_two_entry_sorts_disagree():
    assert [entry.name for entry in sort_entries(ENTRIES)] != \
        [entry.name for entry in legacy_sort_entries(ENTRIES)]


def test_sort_entries_keeps_every_entry():
    assert len(sort_entries(ENTRIES)) == len(ENTRIES)


def test_sort_entries_refuses_something_that_is_not_an_entry():
    with pytest.raises(ExplorerError, match="holds entries"):
        sort_entries(["notes.txt"])


def test_visible_leaves_out_the_hidden_names():
    assert [entry.name for entry in visible(ENTRIES)] == \
        [name for name in MEASURED["visible"]]


def test_visible_holds_no_dot_name():
    assert all(not entry.hidden() for entry in visible(ENTRIES))


def test_hidden_holds_only_the_dot_names():
    assert [entry.name for entry in hidden(ENTRIES)] == [".config",
                                                         ".gitignore"]


def test_the_visible_and_hidden_entries_add_up():
    assert len(visible(ENTRIES)) + len(hidden(ENTRIES)) == len(ENTRIES)


# --------------------------------------------------------------------------- #
# Parsing the bundle
# --------------------------------------------------------------------------- #
def test_parse_listing_reads_three_fields():
    entries = parse_listing("notes.txt | file | 1023\n")
    assert entries == (Entry("notes.txt", "file", 1023),)


def test_parse_listing_accepts_no_spaces():
    assert parse_listing("notes.txt|file|1023")[0].size == 1023


def test_parse_listing_skips_a_comment():
    assert len(parse_listing("; a note\nnotes.txt | file | 1\n")) == 1


def test_parse_listing_skips_blank_lines():
    assert len(parse_listing("\nnotes.txt | file | 1\n\n")) == 1


def test_parse_listing_reads_windows_line_endings():
    text = "a | file | 1\r\nb | dir | 0\r\n"
    assert len(parse_listing(text)) == 2


def test_parse_listing_refuses_a_short_line():
    with pytest.raises(ExplorerError, match="three fields are needed"):
        parse_listing("notes.txt | file\n")


def test_parse_listing_names_the_line_it_could_not_read():
    with pytest.raises(ExplorerError, match="line 2:"):
        parse_listing("a | file | 1\nbroken\n")


def test_parse_listing_refuses_a_word_where_a_size_should_be():
    with pytest.raises(ExplorerError, match="not a whole number of bytes"):
        parse_listing("notes.txt | file | big\n")


def test_parse_listing_refuses_an_unknown_kind():
    with pytest.raises(ExplorerError, match="a kind is"):
        parse_listing("notes.txt | link | 1\n")


def test_parse_listing_refuses_an_empty_bundle():
    with pytest.raises(ExplorerError, match="at least one entry"):
        parse_listing("; nothing\n")


def test_parse_listing_refuses_two_entries_with_one_name():
    with pytest.raises(ExplorerError, match="names are distinct"):
        parse_listing("a | file | 1\na | dir | 0\n")


def test_the_bundled_listing_has_thirteen_entries():
    assert len(ENTRIES) == 13


def test_the_bundled_listing_holds_two_hidden_names():
    assert len(hidden(ENTRIES)) == 2


def test_read_listing_refuses_a_missing_file(tmp_path):
    with pytest.raises(ExplorerError, match="file not found"):
        read_listing(tmp_path / "nope.txt")


def test_read_listing_accepts_its_own_file(tmp_path):
    path = tmp_path / "listing.txt"
    path.write_bytes(b"notes.txt | file | 1\n")
    assert read_listing(path)[0].name == "notes.txt"


def test_the_field_separator_is_a_pipe():
    assert FIELD == "|"


# --------------------------------------------------------------------------- #
# Confinement
# --------------------------------------------------------------------------- #
def test_confine_joins_a_name_to_the_root():
    assert confine("data/site", "notes.txt") == "data/site/notes.txt"


def test_confine_normalises_a_dot_dot_that_stays_inside():
    assert confine("data/site", "docs/../notes.txt") == "data/site/notes.txt"


def test_confine_accepts_a_nested_name():
    assert confine("data/site", "a/b/c.txt") == "data/site/a/b/c.txt"


def test_confine_accepts_a_trailing_slash_on_the_root():
    assert confine("data/site/", "notes.txt") == "data/site/notes.txt"


def test_confine_refuses_a_dot_dot_that_leaves():
    with pytest.raises(ExplorerError, match="leaves 'data/site'"):
        confine("data/site", "../secret.txt")


def test_confine_refuses_a_dot_dot_below_the_root():
    with pytest.raises(ExplorerError, match="leaves"):
        confine("data/site", "docs/../../secret.txt")


def test_confine_refuses_an_absolute_name():
    with pytest.raises(ExplorerError, match="is absolute"):
        confine("data/site", "/etc/passwd")


def test_confine_refuses_a_blank_name():
    with pytest.raises(ExplorerError, match="not blank"):
        confine("data/site", "  ")


def test_confine_refuses_a_number_for_a_name():
    with pytest.raises(ExplorerError, match="a name is text"):
        confine("data/site", 7)


def test_confine_refuses_a_null_byte():
    with pytest.raises(ExplorerError, match="null byte"):
        confine("data/site", "notes\x00.txt")


def test_confine_refuses_a_blank_root():
    with pytest.raises(ExplorerError, match="a root is text, and not blank"):
        confine("  ", "notes.txt")


def test_is_confined_answers_true_for_a_name_inside():
    assert is_confined("data/site", "notes.txt") is True


def test_is_confined_answers_false_for_a_name_outside():
    assert is_confined("data/site", "../secret.txt") is False


def test_the_legacy_join_honours_a_dot_dot():
    assert legacy_normalised("data/site", "../secret.txt") == "data/secret.txt"


def test_the_legacy_join_keeps_an_absolute_name():
    assert legacy_normalised("data/site", "/etc/passwd") == "/etc/passwd"


def test_the_legacy_join_is_the_path_operator():
    assert str(legacy_join("data/site", "n.txt")) == str(Path("data/site") / "n.txt")


def test_a_string_prefix_calls_a_sibling_inside():
    assert legacy_contains("data/site", "data/site-other/x.txt") is True


def test_a_path_prefix_calls_a_sibling_outside():
    assert contains("data/site", "data/site-other/x.txt") is False


def test_contains_accepts_the_root_itself():
    assert contains("data/site", "data/site") is True


def test_contains_accepts_a_name_below_the_root():
    assert contains("data/site", "data/site/notes.txt") is True


def test_contains_refuses_a_parent():
    assert contains("data/site", "data") is False


def test_contains_refuses_a_blank_target():
    with pytest.raises(ExplorerError, match="a target is text, and not blank"):
        contains("data/site", " ")


def test_the_transcribed_guard_is_the_startswith():
    assert LEGACY_CONTAINS == "return str(target).startswith(str(root))"


def test_the_transcribed_listing_is_three_lines():
    assert LEGACY_LISTING.startswith("names = [entry.name for entry in")
    assert "names.sort()" in LEGACY_LISTING


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #
def test_measure_pins_the_natural_order():
    assert MEASURED["natural"] == ["file1.txt", "file2.txt", "file10.txt",
                                   "file20.txt"]


def test_measure_pins_the_legacy_order():
    assert MEASURED["legacy"] == ["file1.txt", "file10.txt", "file2.txt",
                                  "file20.txt"]


def test_measure_pins_both_case_orders():
    assert MEASURED["folded"] == ["apple.txt", "Banana.txt", "Zebra.txt"]
    assert MEASURED["folded_legacy"] == ["Banana.txt", "Zebra.txt", "apple.txt"]


def test_measure_pins_the_casefold_tie():
    assert MEASURED["tie"] == ["STRASSE", "Stra\u00dfe"]


def test_measure_pins_the_bundle_order():
    assert MEASURED["bundle_names"][:2] == ["docs", "pictures"]
    assert MEASURED["bundle_sorted"] == MEASURED["bundle_names"]


def test_measure_records_the_hidden_split():
    assert len(MEASURED["visible"]) == 11
    assert MEASURED["hidden"] == [".config", ".gitignore"]


def test_measure_records_the_escape():
    assert MEASURED["escape_refused"] is True
    assert MEASURED["legacy_escape"] == "data/secret.txt"


def test_measure_records_the_absolute_name():
    assert MEASURED["absolute_refused"] is True


def test_measure_records_the_prefix_trap():
    assert MEASURED["prefix_trap"] == "outside"
    assert MEASURED["legacy_prefix_trap"] == "inside"


def test_measure_records_the_inside_dot_dot():
    assert MEASURED["inside_dotdot"] == "data/site/notes.txt"


def test_measure_pins_both_size_formatters():
    assert MEASURED["size_1280"] == "1.3 KB"
    assert MEASURED["legacy_size_1280"] == "1.2 KB"
    assert MEASURED["size_1"] == "1 B"
    assert MEASURED["legacy_size_1"] == "1.0 B"


def test_measure_reads_nothing_out_of_the_bundle_it_was_not_given():
    small = measure((Entry("notes.txt", "file", 1),))
    assert small["size_1280"] == "1.3 KB" and small["visible"] == ["notes.txt"]


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "digits compare as numbers",
    "the legacy sort compares digits as characters",
    "a listing ignores case",
    "a casefold tie is broken by the raw name",
    "a sort never loses or invents a name",
    "a hidden name is left out until it is asked for",
    "dot dot cannot leave the root",
    "an absolute name is refused",
    "a sibling with the same prefix is outside",
    "dot dot that stays inside is allowed",
    "a size is tenths rounded half up and bytes have none",
]


def real_checks():
    return audit(MEASURED, ENTRIES)


def test_the_audit_holds_eleven_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_listing():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def corrupted(**changes) -> dict:
    payload = dict(MEASURED)
    payload.update(changes)
    return payload


def test_the_audit_catches_a_lexicographic_natural_order():
    checks = audit(corrupted(natural=["file1.txt", "file10.txt", "file2.txt",
                                      "file20.txt"]), ENTRIES)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_a_legacy_sort_that_happened_to_be_right():
    checks = audit(corrupted(legacy=MEASURED["natural"]), ENTRIES)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_a_case_sensitive_listing():
    checks = audit(corrupted(folded=MEASURED["folded_legacy"]), ENTRIES)
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_a_tie_broken_by_case_insensitively():
    checks = audit(corrupted(tie=["Stra\u00dfe", "STRASSE"]), ENTRIES)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_a_sort_that_dropped_a_name():
    dropped = list(MEASURED["bundle_sorted"])[:-1]
    checks = audit(corrupted(bundle_sorted=dropped), ENTRIES)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_a_hidden_name_shown_by_default():
    leaked = MEASURED["visible"] + [".config"]
    checks = audit(corrupted(visible=leaked), ENTRIES)
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_an_escape_that_was_allowed():
    checks = audit(corrupted(escape_refused=False), ENTRIES)
    assert CHECK_NAMES[6] in problems(checks)


def test_the_audit_catches_an_absolute_name_that_was_allowed():
    checks = audit(corrupted(absolute_refused=False), ENTRIES)
    assert CHECK_NAMES[7] in problems(checks)


def test_the_audit_catches_a_string_prefix_guard():
    checks = audit(corrupted(prefix_trap="inside"), ENTRIES)
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_a_dot_dot_that_was_refused_needlessly():
    checks = audit(corrupted(inside_dotdot="refused"), ENTRIES)
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_banker_s_rounding():
    checks = audit(corrupted(size_1280="1.2 KB"), ENTRIES)
    assert CHECK_NAMES[10] in problems(checks)


def test_the_audit_catches_a_byte_shown_with_a_tenth():
    checks = audit(corrupted(size_1="1.0 B"), ENTRIES)
    assert CHECK_NAMES[10] in problems(checks)


def test_a_missing_measurement_is_a_failure_not_a_traceback():
    payload = corrupted()
    del payload["absolute_refused"]
    checks = audit(payload, ENTRIES)
    assert CHECK_NAMES[7] in problems(checks)
    assert len(checks) == len(CHECK_NAMES)


def test_every_check_has_a_negative_control():
    caught = set()
    caught |= set(problems(audit(corrupted(natural=["file10.txt"]), ENTRIES)))
    caught |= set(problems(audit(corrupted(legacy=[]), ENTRIES)))
    caught |= set(problems(audit(corrupted(folded_legacy=[]), ENTRIES)))
    caught |= set(problems(audit(corrupted(tie=[]), ENTRIES)))
    caught |= set(problems(audit(corrupted(bundle_sorted=[]), ENTRIES)))
    caught |= set(problems(audit(corrupted(hidden=[]), ENTRIES)))
    caught |= set(problems(audit(corrupted(escape_refused=False), ENTRIES)))
    caught |= set(problems(audit(corrupted(absolute_refused=False), ENTRIES)))
    caught |= set(problems(audit(corrupted(prefix_trap="inside"), ENTRIES)))
    caught |= set(problems(audit(corrupted(inside_dotdot="refused"), ENTRIES)))
    caught |= set(problems(audit(corrupted(size_1="1.0 B"), ENTRIES)))
    assert caught == set(CHECK_NAMES)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_legacy_listing(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "FILE LAB" in out and "names.sort()" in out


def test_demo_counts_the_disagreeing_positions(capsys):
    run_demo()
    assert "4 of 11 positions disagree" in capsys.readouterr().out


def test_demo_shows_the_prefix_trap(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "outside data/site here, and inside to startswith()" in out


def test_demo_shows_all_eleven_checks(capsys):
    run_demo()
    assert "11/11 checks pass" in capsys.readouterr().out


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


def test_cli_lists_the_visible_entries(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "11 of 13 entr(ies)" in out and ".config" not in out


def test_cli_lists_the_hidden_entries_when_asked(capsys):
    assert cli.main(["--hidden"]) == 0
    out = capsys.readouterr().out
    assert "13 of 13" in out and ".config" in out


def test_cli_sorts_naturally(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert out.index("file2.txt") < out.index("file10.txt")


def test_cli_sorts_the_legacy_way_when_asked(capsys):
    assert cli.main(["--sort", "legacy"]) == 0
    out = capsys.readouterr().out
    assert out.index("file10.txt") < out.index("file2.txt")


def test_cli_resolves_a_name_inside_the_root(capsys):
    assert cli.main(["--resolve", "notes.txt"]) == 0
    assert "data/site/notes.txt" in capsys.readouterr().out


def test_cli_prints_the_size_two_ways(capsys):
    assert cli.main(["--size", "1280"]) == 0
    out = capsys.readouterr().out
    assert "1.3 KB here" in out and "1.2 KB from a float" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 11 and "FAIL" not in out


def test_cli_writes_the_listing_as_json(tmp_path, capsys):
    target = tmp_path / "listing.json"
    assert cli.main(["--hidden", "--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == 13
    assert payload["hidden"] == [".config", ".gitignore"]
    zebra = [entry for entry in payload["entries"]
             if entry["name"] == "Zebra.txt"][0]
    assert zebra["size"] == "1.3 KB" and zebra["legacy_size"] == "1.2 KB"


def test_cli_json_carries_the_measurements_and_checks(tmp_path, capsys):
    target = tmp_path / "listing.json"
    assert cli.main(["--audit", "--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["measurements"]["prefix_trap"] == "outside"
    assert len(payload["checks"]) == 11
    assert all(check["ok"] for check in payload["checks"])


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_refuses_an_escaping_name(capsys):
    assert cli.main(["--resolve", "../secret.txt"]) == 2
    assert "leaves 'data/site'" in capsys.readouterr().err


def test_cli_refuses_an_absolute_name(capsys):
    assert cli.main(["--resolve", "/etc/passwd"]) == 2
    assert "is absolute" in capsys.readouterr().err


def test_cli_refuses_a_negative_size(capsys):
    assert cli.main(["--size", "-4"]) == 2
    assert "not negative" in capsys.readouterr().err


def test_cli_refuses_a_missing_listing(tmp_path, capsys):
    assert cli.main(["--listing", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_refuses_an_unknown_order(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--sort", "folded"])
    assert raised.value.code == 2


def test_cli_refuses_a_size_that_is_not_a_number(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--size", "big"])
    assert raised.value.code == 2


def test_the_module_exports_the_names_it_is_tested_through():
    assert module.UNITS == UNITS
    assert module.KINDS == ("file", "dir")
    assert os.sep in ("\\", "/")
