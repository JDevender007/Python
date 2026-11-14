"""Tests for Journal_Manager: legacy bugs, entries, storage, queries and CLI."""

from __future__ import annotations

import dataclasses
import datetime
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import journal                                            # noqa: E402
import main as cli                                        # noqa: E402
from journal import (                                     # noqa: E402
    DATA_FILE,
    DATE_FORMAT,
    LEGACY_ALIGNED,
    LEGACY_RUNNABLE,
    LEGACY_SOURCE,
    Entry,
    JournalError,
    add,
    between,
    by_tag,
    clean_tags,
    dumps,
    load,
    next_id,
    parse_date,
    render,
    render_entry,
    run_demo,
    save,
    search,
    sort_entries,
    stats,
    tag_counts,
)

DAY = datetime.date


def make(id_=1, date="2024-03-04", title="Title", body="", tags=()):
    return Entry(id=id_, date=parse_date(date), title=title, body=body,
                 tags=tags)


@pytest.fixture()
def entries():
    return [
        make(1, "2024-03-04", "First light", "Set up the bench.", ["setup"]),
        make(2, "2024-03-06", "Rain", "Read the manual.", ["reading"]),
        make(3, "2024-03-09", "Shelf done", "Two shelves fit.", ["build"]),
    ]


# --------------------------------------------------------------------------- #
# The legacy program
# --------------------------------------------------------------------------- #
def test_legacy_source_does_not_compile():
    with pytest.raises(SyntaxError, match="invalid syntax"):
        compile(LEGACY_SOURCE, "<legacy>", "exec")


def test_legacy_else_is_indented_under_the_with_block():
    # the misindented `else` is the error the parser reports first
    lines = LEGACY_SOURCE.splitlines()
    index = lines.index("    else:")
    for_line = next(line for line in lines if line.strip().startswith("for "))
    assert len(for_line) - len(for_line.lstrip()) == 8
    assert len(lines[index]) - len(lines[index].lstrip()) == 4


def test_aligned_source_still_does_not_compile():
    with pytest.raises(SyntaxError, match="outside loop"):
        compile(LEGACY_ALIGNED, "<legacy>", "exec")


def test_runnable_source_compiles():
    compile(LEGACY_RUNNABLE, "<legacy>", "exec")


def test_legacy_search_appends_the_message_even_on_a_hit():
    assert journal.legacy_search("coffee", ["bought coffee"]) == \
        ["bought coffee", "No entries found"]


def test_legacy_search_on_a_miss():
    assert journal.legacy_search("banana", ["bought coffee"]) == \
        ["No entries found"]


def test_legacy_search_on_no_lines():
    assert journal.legacy_search("x", []) == ["No entries found"]


# --------------------------------------------------------------------------- #
# Dates and tags
# --------------------------------------------------------------------------- #
def test_parse_date_accepts_iso():
    assert parse_date("2024-03-04") == DAY(2024, 3, 4)


def test_parse_date_accepts_a_date_object():
    assert parse_date(DAY(2024, 3, 4)) == DAY(2024, 3, 4)


def test_parse_date_accepts_a_datetime():
    assert parse_date(datetime.datetime(2024, 3, 4, 15, 30)) == DAY(2024, 3, 4)


def test_parse_date_strips_surrounding_space():
    assert parse_date("  2024-03-04 ") == DAY(2024, 3, 4)


@pytest.mark.parametrize("bad", ["2024-3-4", "04/03/2024", "2024-02-31",
                                 "20240304", "", "yesterday"])
def test_parse_date_refuses_non_iso(bad):
    with pytest.raises(JournalError, match="is not"):
        parse_date(bad)


def test_parse_date_refuses_non_text():
    with pytest.raises(JournalError, match="must be a string"):
        parse_date(20240304)


def test_date_format_constant_is_iso():
    assert DATE_FORMAT == "%Y-%m-%d"


def test_clean_tags_casefolds_and_sorts():
    assert clean_tags(["Zeta", "alpha"]) == ("alpha", "zeta")


def test_clean_tags_dedupes():
    assert clean_tags(["build", "Build", "BUILD"]) == ("build",)


def test_clean_tags_strips_hashes_and_blanks():
    assert clean_tags(["#work", " ", ""]) == ("work",)


def test_clean_tags_of_none_is_empty():
    assert clean_tags(None) == ()


def test_clean_tags_accepts_a_string():
    assert clean_tags("a, b c") == ("a", "b", "c")


def test_clean_tags_refuses_an_inner_space():
    with pytest.raises(JournalError, match="contains whitespace"):
        clean_tags(["two words"])


def test_clean_tags_refuses_a_non_string():
    with pytest.raises(JournalError, match="is not a string"):
        clean_tags([7])


# --------------------------------------------------------------------------- #
# Entries
# --------------------------------------------------------------------------- #
def test_entry_trims_title_and_body():
    entry = make(title="  Title  ", body="  body  ")
    assert entry.title == "Title" and entry.body == "body"


def test_entry_normalises_tags_on_construction():
    assert make(tags=["B", "a", "a "]).tags == ("a", "b")


def test_entry_is_frozen():
    entry = make()
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.title = "new"                              # type: ignore[misc]

def test_entry_refuses_id_zero():
    with pytest.raises(JournalError, match="must be positive"):
        Entry(id=0, date=DAY(2024, 1, 1), title="x")


def test_entry_refuses_a_non_integer_id():
    with pytest.raises(JournalError, match="must be an integer"):
        Entry(id="1", date=DAY(2024, 1, 1), title="x")    # type: ignore[arg-type]


def test_entry_refuses_a_blank_title():
    with pytest.raises(JournalError, match="must not be empty"):
        Entry(id=1, date=DAY(2024, 1, 1), title="   ")


def test_entry_refuses_a_string_date():
    with pytest.raises(JournalError, match="must be a datetime.date"):
        Entry(id=1, date="2024-01-01", title="x")         # type: ignore[arg-type]


def test_entry_counts_words():
    assert make(title="One two", body="three four").words() == 4


def test_entry_word_count_of_a_bare_title():
    assert make(title="Solo").words() == 1


def test_entry_matches_title_case_insensitively():
    assert make(title="Shelf").matches("shelf") is True


def test_entry_matches_body():
    assert make(title="a", body="two shelf units fit").matches("SHELF") is True


def test_entry_matches_a_tag():
    assert make(tags=["workshop"]).matches("work") is True


def test_entry_does_not_match_absent_text():
    assert make(title="a", body="b").matches("zzz") is False


def test_entry_rejects_an_empty_search():
    with pytest.raises(JournalError, match="must not be empty"):
        make().matches("  ")


def test_entry_round_trips_through_a_dict():
    entry = make(4, "2024-05-06", "T", "B", ["x"])
    assert Entry.from_dict(entry.to_dict()) == entry


def test_entry_dict_has_iso_date():
    assert make().to_dict()["date"] == "2024-03-04"


def test_from_dict_refuses_missing_fields():
    with pytest.raises(JournalError, match="missing date"):
        Entry.from_dict({"id": 1, "title": "x"})


def test_from_dict_refuses_unknown_fields():
    with pytest.raises(JournalError, match="unknown field"):
        Entry.from_dict({"id": 1, "date": "2024-01-01", "title": "x",
                         "mood": "y"})


def test_from_dict_refuses_a_non_object():
    with pytest.raises(JournalError, match="must be a JSON object"):
        Entry.from_dict([1, 2])


def test_sort_entries_is_by_date_then_id():
    later = make(1, "2024-05-01")
    same_day_low = make(2, "2024-04-01")
    same_day_high = make(9, "2024-04-01")
    assert sort_entries([later, same_day_high, same_day_low]) == \
        [same_day_low, same_day_high, later]


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def test_save_and_load_round_trip(tmp_path, entries):
    path = tmp_path / "j.jsonl"
    save(path, entries)
    assert load(path) == entries


def test_save_writes_one_line_per_entry(tmp_path, entries):
    path = tmp_path / "j.jsonl"
    save(path, entries)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert all(json.loads(line)["id"] for line in lines)


def test_save_is_byte_identical_on_a_second_write(tmp_path, entries):
    path = tmp_path / "j.jsonl"
    save(path, entries)
    first = path.read_bytes()
    save(path, load(path))
    assert path.read_bytes() == first


def test_dumps_is_deterministic(entries):
    assert dumps(entries) == dumps(list(reversed(entries)))


def test_dumps_ends_with_a_newline(entries):
    assert dumps(entries).endswith("\n")


def test_load_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "j.jsonl"
    path.write_text('# a comment\n\n{"id": 1, "date": "2024-01-01", '
                    '"title": "a"}\n', encoding="utf-8")
    assert len(load(path)) == 1


def test_load_reports_a_damaged_line(tmp_path):
    path = tmp_path / "j.jsonl"
    path.write_text('{"id": 1, "date": "2024-01-01", "title": "a"}\n'
                    '{not json}\n', encoding="utf-8")
    with pytest.raises(JournalError, match="line 2"):
        load(path)


def test_load_reports_a_bad_date_by_line(tmp_path):
    path = tmp_path / "j.jsonl"
    path.write_text('{"id": 1, "date": "1 January", "title": "a"}\n',
                    encoding="utf-8")
    with pytest.raises(JournalError, match="line 1"):
        load(path)


def test_load_refuses_a_duplicate_id(tmp_path):
    path = tmp_path / "j.jsonl"
    path.write_text('{"id": 1, "date": "2024-01-01", "title": "a"}\n'
                    '{"id": 1, "date": "2024-01-02", "title": "b"}\n',
                    encoding="utf-8")
    with pytest.raises(JournalError, match="repeats id 1"):
        load(path)


def test_load_of_a_missing_file(tmp_path):
    with pytest.raises(JournalError, match="not found"):
        load(tmp_path / "nope.jsonl")


def test_save_refuses_a_duplicate_id(tmp_path, entries):
    with pytest.raises(JournalError, match="appears twice"):
        save(tmp_path / "j.jsonl", [entries[0], entries[0]])


def test_save_leaves_no_temporary_file(tmp_path, entries):
    save(tmp_path / "j.jsonl", entries)
    assert [path.name for path in tmp_path.iterdir()] == ["j.jsonl"]


def test_save_creates_missing_directories(tmp_path, entries):
    path = tmp_path / "a" / "b" / "j.jsonl"
    save(path, entries)
    assert path.is_file()


# --------------------------------------------------------------------------- #
# Mutations and queries
# --------------------------------------------------------------------------- #
def test_next_id_of_empty_is_one():
    assert next_id([]) == 1


def test_next_id_is_one_past_the_maximum(entries):
    assert next_id(entries) == 4


def test_next_id_does_not_reuse_a_gap():
    assert next_id([make(1), make(5)]) == 6


def test_add_returns_a_new_list(entries):
    grown = add(entries, "2024-04-01", "New")
    assert len(grown) == 4
    assert len(entries) == 3


def test_add_assigns_the_next_id(entries):
    assert add(entries, "2024-04-01", "New")[-1].id == 4


def test_add_keeps_date_order():
    grown = add([make(1, "2024-05-01")], "2024-01-01", "Early")
    assert [entry.date for entry in grown] == [DAY(2024, 1, 1), DAY(2024, 5, 1)]


def test_add_normalises_tags(entries):
    grown = add(entries, "2024-04-01", "New", tags=["B", "a"])
    assert grown[-1].tags == ("a", "b")


def test_add_refuses_a_bad_date(entries):
    with pytest.raises(JournalError, match="is not"):
        add(entries, "1 April", "New")


def test_search_is_case_insensitive(entries):
    assert [entry.id for entry in search(entries, "SHELF")] == [3]


def test_search_finds_in_the_body(entries):
    assert [entry.id for entry in search(entries, "manual")] == [2]


def test_search_finds_a_tag(entries):
    assert [entry.id for entry in search(entries, "reading")] == [2]


def test_search_with_no_matches_is_empty(entries):
    assert search(entries, "banana") == []


def test_search_of_an_empty_journal_is_empty():
    assert search([], "anything") == []


@pytest.mark.parametrize("bad", ["", "   "])
def test_search_refuses_a_blank_term(entries, bad):
    with pytest.raises(JournalError, match="must not be empty"):
        search(entries, bad)


def test_search_refuses_a_non_string(entries):
    with pytest.raises(JournalError, match="must not be empty"):
        search(entries, None)


def test_by_tag_is_case_insensitive(entries):
    assert [entry.id for entry in by_tag(entries, "READING")] == [2]


def test_by_tag_with_no_match(entries):
    assert by_tag(entries, "nothing") == []


def test_by_tag_refuses_an_empty_tag(entries):
    with pytest.raises(JournalError, match="must not be empty"):
        by_tag(entries, "  ")


def test_by_tag_refuses_several_tags(entries):
    with pytest.raises(JournalError, match="expected one tag"):
        by_tag(entries, "a b")


def test_between_is_inclusive(entries):
    assert len(between(entries, "2024-03-04", "2024-03-09")) == 3


def test_between_narrows(entries):
    assert [entry.id for entry in between(entries, "2024-03-05",
                                          "2024-03-08")] == [2]


def test_between_a_single_day(entries):
    assert between(entries, "2024-03-09", "2024-03-09") == [entries[2]]


def test_between_refuses_a_reversed_range(entries):
    with pytest.raises(JournalError, match="is after end"):
        between(entries, "2024-03-09", "2024-03-01")


def test_between_refuses_a_bad_date(entries):
    with pytest.raises(JournalError, match="is not"):
        between(entries, "March", "2024-03-09")


def test_tag_counts_sorts_by_use_then_name():
    rows = [make(1, tags=["b", "a"]), make(2, tags=["a"])]
    assert tag_counts(rows) == {"a": 2, "b": 1}


def test_tag_counts_of_empty():
    assert tag_counts([]) == {}


def test_stats_of_a_journal(entries):
    summary = stats(entries)
    assert summary["entries"] == 3
    assert summary["first"] == "2024-03-04"
    assert summary["last"] == "2024-03-09"
    assert summary["tags"] == 3


def test_stats_of_an_empty_journal_uses_nulls():
    summary = stats([])
    assert summary == {"entries": 0, "first": None, "last": None, "words": 0,
                       "tags": 0, "longest": 0}


def test_stats_words_match_the_entries(entries):
    assert stats(entries)["words"] == sum(entry.words() for entry in entries)


def test_stats_longest_is_the_biggest_entry(entries):
    assert stats(entries)["longest"] == max(entry.words() for entry in entries)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_entry_shows_id_date_and_title(entries):
    text = render_entry(entries[0])
    assert "#1" in text and "2024-03-04" in text and "First light" in text


def test_render_entry_shows_tags(entries):
    assert "[setup]" in render_entry(entries[0])


def test_render_of_an_empty_journal():
    assert render([]) == "  (no entries)"


def test_render_shows_every_entry(entries):
    text = render(entries)
    assert all(entry.title in text for entry in entries)


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
def test_bundled_journal_has_six_entries():
    assert len(load(DATA_FILE)) == 6


def test_bundled_journal_ids_are_sequential():
    assert [entry.id for entry in load(DATA_FILE)] == [1, 2, 3, 4, 5, 6]


def test_bundled_journal_is_in_date_order():
    dates = [entry.date for entry in load(DATA_FILE)]
    assert dates == sorted(dates)


def test_bundled_journal_entries_all_have_titles():
    assert all(entry.title for entry in load(DATA_FILE))


def test_bundled_journal_has_tags():
    assert stats(load(DATA_FILE))["tags"] == 6


def test_bundled_journal_finds_shelf():
    assert len(search(load(DATA_FILE), "shelf")) >= 1


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


def test_demo_reports_both_syntax_errors(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "invalid syntax" in out
    assert "outside loop" in out


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_bundled_journal(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "6 entries" in out
    assert "First light" in out


def test_cli_search(capsys):
    assert cli.main(["--search", "shelf"]) == 0
    out = capsys.readouterr().out
    assert "match" in out
    assert "Shelf done" in out


def test_cli_search_with_no_matches(capsys):
    assert cli.main(["--search", "zzzz"]) == 0
    assert "0 matches" in capsys.readouterr().out


def test_cli_tag(capsys):
    assert cli.main(["--tag", "workshop"]) == 0
    out = capsys.readouterr().out
    assert "Measure twice" in out


def test_cli_range(capsys):
    assert cli.main(["--from", "2024-03-05", "--to", "2024-03-12"]) == 0
    out = capsys.readouterr().out
    assert "Rain all day" in out and "Measure twice" in out


def test_cli_range_with_only_a_start(capsys):
    assert cli.main(["--from", "2024-03-15"]) == 0
    out = capsys.readouterr().out
    assert "2 matches" in out


def test_cli_stats(capsys):
    assert cli.main(["--stats"]) == 0
    out = capsys.readouterr().out
    assert "entries" in out and "6" in out


def test_cli_tags(capsys):
    assert cli.main(["--tags"]) == 0
    out = capsys.readouterr().out
    assert "workshop" in out


def test_cli_add_dry_run(capsys, tmp_path):
    path = tmp_path / "j.jsonl"
    save(path, [make(1)])
    assert cli.main(["--file", str(path), "--add", "New", "--date",
                     "2024-04-01", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "not written, dry run" in out
    assert len(load(path)) == 1


def test_cli_add_writes(capsys, tmp_path):
    path = tmp_path / "j.jsonl"
    save(path, [make(1)])
    assert cli.main(["--file", str(path), "--add", "New", "--date",
                     "2024-04-01", "--body", "text", "--add-tags", "a,b"]) == 0
    capsys.readouterr()
    entries = load(path)
    assert len(entries) == 2
    assert entries[-1].title == "New"
    assert entries[-1].tags == ("a", "b")


def test_cli_add_with_a_bad_date_exits_two(tmp_path, capsys):
    path = tmp_path / "j.jsonl"
    save(path, [make(1)])
    assert cli.main(["--file", str(path), "--add", "New",
                     "--date", "1 April"]) == 2
    assert "is not" in capsys.readouterr().err


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "invalid syntax" in out and "outside loop" in out


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.jsonl"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_json_list(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "list"
    assert payload["count"] == 6
    assert payload["entries"][0]["date"] == "2024-03-04"


def test_cli_json_stats(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--stats", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["stats"]["entries"] == 6


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--stats", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_module_exposes_its_data_file():
    assert journal.DATA_FILE.name == "journal.jsonl"
