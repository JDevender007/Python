"""Tests for Log_File_Analyzer: a level is a field, an entry is not a line."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
from analyzer import (                                        # noqa: E402
    LEGACY_CHAIN,
    LEGACY_EXTENSIONS,
    LEGACY_LINE,
    LEVELS,
    LOGS,
    Analysis,
    BadLine,
    Entry,
    FileReport,
    LogError,
    analyze,
    check_folder,
    legacy_classify,
    legacy_counts,
    legacy_lines,
    legacy_unknowns,
    read_file,
    report_rows,
    report_text,
    run_demo,
    search,
    split_line,
)

WHEN = datetime(2026, 5, 11, 8, 0, 1)


def a_log(folder: Path, name: str, text: str) -> Path:
    """Write exact bytes: no \\r\\n translation."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


def an_entry(level: str = "INFO", message: str = "hello", line: int = 1,
             file: str = "a.log", when: datetime = WHEN,
             continuations: tuple[str, ...] = ()) -> Entry:
    return Entry(file, line, when, level, message, continuations)


# --------------------------------------------------------------------------- #
# split_line
# --------------------------------------------------------------------------- #
def test_an_entry_line_splits_into_three_parts():
    when, level, message = split_line("2026-05-11 08:00:01 INFO Starting")
    assert level == "INFO" and message == "Starting"
    assert when == datetime(2026, 5, 11, 8, 0, 1)


def test_a_line_without_a_message_still_splits():
    when, level, message = split_line("2026-05-11 08:00:01 WARNING")
    assert level == "WARNING" and message == ""


def test_a_trailing_newline_is_ignored():
    assert split_line("2026-05-11 08:00:01 INFO x\n")[1] == "INFO"


def test_a_trailing_carriage_return_is_ignored():
    assert split_line("2026-05-11 08:00:01 INFO x\r")[1] == "INFO"


def test_a_message_may_contain_spaces_and_colons():
    message = split_line("2026-05-11 08:00:01 ERROR a: b: c")[2]
    assert message == "a: b: c"


def test_a_line_with_no_timestamp_is_refused():
    with pytest.raises(LogError, match="does not start with a timestamp"):
        split_line("INFO Starting")


def test_a_prose_line_is_refused():
    with pytest.raises(LogError, match="does not start with a timestamp"):
        split_line("This file ends in .log and holds no entries.")


def test_an_unknown_level_is_refused():
    with pytest.raises(LogError, match="is not a level"):
        split_line("2026-05-11 08:00:01 TRACE something")


def test_a_bracketed_token_is_not_a_level():
    with pytest.raises(LogError, match="is not a level"):
        split_line("2026-05-11 08:00:01 [pid 41] trailer")


def test_a_level_in_lower_case_is_not_a_level():
    with pytest.raises(LogError, match="is not a level"):
        split_line("2026-05-11 08:00:01 info starting")


def test_an_impossible_date_is_refused():
    with pytest.raises(LogError, match="not a real date"):
        split_line("2026-02-30 08:00:01 INFO nonsense")


def test_an_impossible_time_is_refused():
    with pytest.raises(LogError, match="not a real date"):
        split_line("2026-05-11 25:00:01 INFO nonsense")


def test_a_date_in_another_format_is_refused():
    with pytest.raises(LogError):
        split_line("11/05/2026 08:00:01 INFO slashes")


# --------------------------------------------------------------------------- #
# Entry
# --------------------------------------------------------------------------- #
def test_an_entry_keeps_its_parts():
    entry = an_entry()
    assert (entry.level, entry.message, entry.line) == ("INFO", "hello", 1)


def test_an_entry_refuses_an_unknown_level():
    with pytest.raises(LogError, match="is not a level"):
        an_entry("NOTICE")


def test_an_entry_refuses_a_line_below_one():
    with pytest.raises(LogError, match="starts at 1"):
        an_entry(line=0)


def test_an_entry_needs_a_timestamp():
    with pytest.raises(LogError, match="needs a timestamp"):
        an_entry(when="2026-05-11 08:00:01")


def test_an_entry_text_is_the_message_alone():
    assert an_entry(message="hello").text == "hello"


def test_an_entry_text_includes_its_continuations():
    entry = an_entry(message="boom", continuations=("Traceback", "  File x"))
    assert entry.text == "boom\nTraceback\n  File x"


def test_an_entry_counts_its_physical_lines():
    assert an_entry(continuations=("a", "b")).lines == 3


def test_a_bare_entry_is_one_line():
    assert an_entry().lines == 1


def test_mentions_finds_a_whole_level_word():
    assert an_entry(message="no error detected").mentions() == ("ERROR",)


def test_mentions_ignores_a_level_inside_a_longer_word():
    assert an_entry(message="errors 0").mentions() == ()


def test_mentions_finds_several_levels():
    assert an_entry(message="warning then error").mentions() == \
        ("WARNING", "ERROR")


def test_mentions_reads_the_continuations_too():
    assert an_entry(message="boom", continuations=("ERROR: x",)).mentions() == \
        ("ERROR",)


def test_an_entry_prints_its_stamp_and_level():
    assert str(an_entry(message="starting")) == \
        "2026-05-11 08:00:01 INFO     starting"


def test_an_entry_dict_holds_every_field():
    payload = an_entry(message="m", continuations=("c",)).to_dict()
    assert payload == {"file": "a.log", "line": 1,
                       "when": "2026-05-11 08:00:01", "level": "INFO",
                       "message": "m", "continuations": ["c"]}


def test_an_entry_is_frozen():
    entry = an_entry()
    with pytest.raises(Exception):
        entry.level = "ERROR"                     # type: ignore[misc]


# --------------------------------------------------------------------------- #
# BadLine
# --------------------------------------------------------------------------- #
def test_a_bad_line_keeps_its_reason():
    bad = BadLine("a.log", 3, "garbage", "the line does not start")
    assert str(bad) == "a.log:3  garbage  (the line does not start)"


def test_a_bad_line_needs_a_reason():
    with pytest.raises(LogError, match="needs a reason"):
        BadLine("a.log", 1, "x", "")


def test_a_bad_line_refuses_a_line_below_one():
    with pytest.raises(LogError, match="starts at 1"):
        BadLine("a.log", 0, "x", "why")


def test_a_bad_line_dict_holds_every_field():
    assert BadLine("a.log", 2, "x", "why").to_dict() == {
        "file": "a.log", "line": 2, "text": "x", "reason": "why"}


# --------------------------------------------------------------------------- #
# FileReport
# --------------------------------------------------------------------------- #
def a_report(entries=(), bad=(), nonblank=1, blobs=10, name="a.log"):
    return FileReport(name, tuple(entries), tuple(bad), nonblank, blobs)


def test_a_file_report_counts_every_level():
    report = a_report((an_entry("INFO"), an_entry("ERROR")))
    assert report.counts() == {"DEBUG": 0, "INFO": 1, "WARNING": 0,
                               "ERROR": 1, "CRITICAL": 0}


def test_a_file_report_with_no_entries_counts_all_zeros():
    assert a_report().counts() == {level: 0 for level in LEVELS}


def test_a_file_report_sums_its_continuations():
    report = a_report((an_entry(continuations=("a", "b")),
                       an_entry(continuations=("c",))))
    assert report.continuations == 3


def test_a_file_report_dict_holds_the_shape():
    payload = a_report((an_entry(),), name="x.log").to_dict()
    assert payload["file"] == "x.log" and payload["entries"] == 1
    assert payload["levels"]["INFO"] == 1 and payload["bytes"] == 10


# --------------------------------------------------------------------------- #
# read_file
# --------------------------------------------------------------------------- #
def test_read_file_refuses_a_missing_file(tmp_path):
    with pytest.raises(LogError, match="not a file"):
        read_file(tmp_path / "nope.log")


def test_read_file_refuses_a_directory(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(LogError, match="not a file"):
        read_file(folder)


def test_read_file_reads_one_entry(tmp_path):
    path = a_log(tmp_path, "a.log", "2026-05-11 08:00:01 INFO hi\n")
    report = read_file(path)
    assert len(report.entries) == 1 and report.entries[0].message == "hi"


def test_read_file_keeps_a_continuation_with_its_entry(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "2026-05-11 08:00:01 ERROR boom\nTraceback:\n  File x\n")
    report = read_file(path)
    assert len(report.entries) == 1
    assert report.entries[0].continuations == ("Traceback:", "  File x")


def test_a_continuation_never_becomes_an_entry(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "2026-05-11 08:00:01 ERROR boom\nPermissionError: denied\n")
    report = read_file(path)
    assert len(report.entries) == 1 and report.bad == ()


def test_read_file_keeps_a_malformed_line_and_its_reason(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "2026-05-11 08:00:01 INFO ok\n2026-05-11 08:00:02 --- x ---\n")
    report = read_file(path)
    assert len(report.entries) == 1 and len(report.bad) == 1
    assert "'---' is not a level" in report.bad[0].reason


def test_a_prose_line_with_no_open_entry_is_malformed(tmp_path):
    path = a_log(tmp_path, "notes.log", "just a sentence\n")
    report = read_file(path)
    assert report.entries == () and len(report.bad) == 1
    assert "does not start with a timestamp" in report.bad[0].reason


def test_a_prose_line_after_an_entry_becomes_a_continuation(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "2026-05-11 08:00:01 INFO ok\njust a sentence\n")
    report = read_file(path)
    assert len(report.entries) == 1
    assert report.entries[0].continuations == ("just a sentence",)


def test_a_malformed_timestamped_line_closes_the_entry(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "2026-05-11 08:00:01 INFO ok\n2026-05-11 08:00:02 ZZZ x\n"
                 "2026-05-11 08:00:03 INFO next\n")
    report = read_file(path)
    assert len(report.entries) == 2 and len(report.bad) == 1
    assert report.entries[0].continuations == ()


def test_blank_lines_are_not_counted(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "2026-05-11 08:00:01 INFO ok\n\n\n2026-05-11 08:00:02 INFO x\n")
    report = read_file(path)
    assert report.nonblank == 2 and len(report.entries) == 2
    assert report.bad == ()


def test_a_blank_line_does_not_close_a_traceback(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "2026-05-11 08:00:01 ERROR boom\n\n  File x\n")
    report = read_file(path)
    assert report.entries[0].continuations == ("  File x",)


def test_the_last_entry_is_closed_at_the_end_of_the_file(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "2026-05-11 08:00:01 ERROR boom\n  File x\n")
    report = read_file(path)
    assert report.entries[0].continuations == ("  File x",)


def test_line_numbers_are_one_based_and_physical(tmp_path):
    path = a_log(tmp_path, "a.log",
                 "\n2026-05-11 08:00:01 INFO ok\n\n2026-05-11 08:00:02 INFO x\n")
    report = read_file(path)
    assert [entry.line for entry in report.entries] == [2, 4]


def test_read_file_counts_the_bytes(tmp_path):
    path = a_log(tmp_path, "a.log", "2026-05-11 08:00:01 INFO hi\n")
    assert read_file(path).blobs == 28


def test_read_file_keeps_the_file_name(tmp_path):
    path = a_log(tmp_path, "worker.log", "2026-05-11 08:00:01 INFO hi\n")
    assert read_file(path).name == "worker.log"


def test_an_empty_file_has_no_entries_and_no_malformed_lines(tmp_path):
    path = a_log(tmp_path, "empty.log", "")
    report = read_file(path)
    assert len(report.entries) == 0 and report.nonblank == 0


def test_a_carriage_return_does_not_break_the_timestamp(tmp_path):
    path = tmp_path / "crlf.log"
    path.write_bytes(b"2026-05-11 08:00:01 INFO hi\r\n")
    report = read_file(path)
    assert len(report.entries) == 1 and report.entries[0].message == "hi"


def test_a_timestamp_inside_a_message_starts_no_new_entry(tmp_path):
    path = a_log(tmp_path, "a.log",
                 '2026-05-11 08:00:01 INFO quoted "2026-05-11 07:00:00 ERROR x"\n')
    report = read_file(path)
    assert len(report.entries) == 1 and report.entries[0].level == "INFO"


# --------------------------------------------------------------------------- #
# analyze / check_folder
# --------------------------------------------------------------------------- #
def test_check_folder_refuses_a_missing_folder(tmp_path):
    with pytest.raises(LogError, match="folder not found"):
        check_folder(tmp_path / "nope")


def test_check_folder_refuses_a_file(tmp_path):
    target = a_log(tmp_path, "a.log", "")
    with pytest.raises(LogError, match="is a file, not a folder"):
        check_folder(target)


def test_analyze_refuses_a_missing_folder(tmp_path):
    with pytest.raises(LogError, match="folder not found"):
        analyze(tmp_path / "nope")


def test_analyze_of_an_empty_folder_is_empty(tmp_path):
    analysis = analyze(tmp_path)
    assert len(analysis) == 0 and analysis.files == ()


def test_analyze_reads_every_file_in_name_order(tmp_path):
    a_log(tmp_path, "b.log", "2026-05-11 08:00:01 INFO b\n")
    a_log(tmp_path, "A.log", "2026-05-11 08:00:01 INFO a\n")
    assert [report.name for report in analyze(tmp_path).files] == \
        ["A.log", "b.log"]


def test_analyze_ignores_subfolders(tmp_path):
    a_log(tmp_path, "a.log", "2026-05-11 08:00:01 INFO a\n")
    (tmp_path / "old").mkdir()
    assert len(analyze(tmp_path).files) == 1


def test_analyze_reads_files_with_any_suffix(tmp_path):
    a_log(tmp_path, "a.txt", "2026-05-11 08:00:01 INFO a\n")
    assert len(analyze(tmp_path)) == 1


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def an_analysis(entries=(), bad=(), nonblank=1, name="a.log"):
    report = FileReport(name, tuple(entries), tuple(bad), nonblank, 10)
    return Analysis(Path("logs"), (report,))


def test_an_analysis_counts_its_entries(tmp_path):
    assert len(an_analysis((an_entry(), an_entry()))) == 2


def test_iteration_walks_the_entries():
    assert [entry.message for entry in an_analysis((an_entry(message="a"),
                                                    an_entry(message="b")))] \
        == ["a", "b"]


def test_an_analysis_repr_names_the_three_numbers():
    assert repr(an_analysis((an_entry(),))) == \
        "<Analysis 1 files, 1 entries, 1 counted, 0 malformed>"


def test_counts_include_every_level():
    assert an_analysis((an_entry("DEBUG"), an_entry("CRITICAL"))).counts() == {
        "DEBUG": 1, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 1}


def test_file_counts_names_each_file():
    assert list(an_analysis((an_entry(),)).file_counts()) == ["a.log"]


def test_continuations_are_summed_across_files():
    assert an_analysis((an_entry(continuations=("a",)),)).continuations == 1


def test_nonblank_is_summed_across_files():
    assert an_analysis((an_entry(),), nonblank=7).nonblank == 7


def test_blobs_is_summed_across_files():
    assert an_analysis((an_entry(),)).blobs == 10


def test_bad_collects_every_malformed_line():
    bad = (BadLine("a.log", 1, "x", "why"),)
    assert len(an_analysis(bad=bad).bad) == 1


def test_span_returns_the_first_and_last_stamps():
    later = datetime(2026, 5, 11, 8, 1, 1)
    analysis = an_analysis((an_entry(when=later), an_entry(when=WHEN)))
    first, last, seconds = analysis.span()
    assert (first, last, seconds) == (WHEN, later, 60)


def test_span_of_an_empty_analysis_is_refused():
    with pytest.raises(LogError, match="no span"):
        an_analysis().span()


def test_the_summary_holds_every_count():
    summary = an_analysis((an_entry(),), nonblank=2).summary()
    assert summary == {"root": "logs", "files": 1, "entries": 1, "nonblank": 2,
                       "blobs": 10, "continuations": 0, "malformed": 0,
                       "DEBUG": 0, "INFO": 1, "WARNING": 0, "ERROR": 0,
                       "CRITICAL": 0}


def test_to_dict_holds_the_four_sections():
    assert set(an_analysis((an_entry(),)).to_dict()) == \
        {"summary", "files", "entries", "malformed"}


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #
def test_a_clean_analysis_passes_every_check():
    analysis = an_analysis((an_entry(),), nonblank=1)
    assert len(analysis.verify()) == 6 and analysis.problems() == []


def test_the_checks_are_named():
    assert [name for name, _ in an_analysis((an_entry(),)).verify()] == [
        "every entry names one of the five levels",
        "no file's timestamps go backwards",
        "the files are listed in name order",
        "no line is both an entry and a malformed line",
        "entries + continuations + malformed equals the non-blank lines",
        "every malformed line has text and a reason"]


def test_the_audit_catches_an_unknown_level():
    analysis = an_analysis((an_entry(),))
    object.__setattr__(analysis.entries[0], "level", "NOTICE")
    assert analysis.problems() == ["every entry names one of the five levels"]


def test_the_audit_catches_timestamps_going_backwards():
    later = datetime(2026, 5, 11, 9, 0, 0)
    analysis = an_analysis((an_entry(when=later), an_entry(when=WHEN)),
                           nonblank=2)
    assert analysis.problems() == ["no file's timestamps go backwards"]


def test_the_audit_catches_files_out_of_order():
    first = FileReport("b.log", (), (), 0, 1)
    second = FileReport("a.log", (), (), 0, 1)
    assert Analysis(Path("."), (first, second)).problems() == \
        ["the files are listed in name order"]


def test_the_audit_catches_one_line_counted_twice():
    entry = an_entry(line=1)
    bad = BadLine("a.log", 1, "x", "why")
    analysis = an_analysis((entry,), bad=(bad,), nonblank=2)
    assert analysis.problems() == ["no line is both an entry and a malformed "
                                   "line"]


def test_the_audit_catches_a_lost_line():
    analysis = an_analysis((an_entry(),), nonblank=5)
    assert analysis.problems() == \
        ["entries + continuations + malformed equals the non-blank lines"]


def test_the_audit_catches_a_malformed_line_with_no_text():
    bad = BadLine("a.log", 2, "x", "why")
    analysis = an_analysis(bad=(bad,), nonblank=1)
    object.__setattr__(analysis.bad[0], "text", "   ")
    assert analysis.problems() == ["every malformed line has text and a reason"]


def test_verify_is_repeatable():
    analysis = an_analysis((an_entry(),))
    assert analysis.verify() == analysis.verify()


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #
def test_search_finds_a_whole_word():
    analysis = an_analysis((an_entry(message="no error detected"),))
    assert len(search(analysis, "error")) == 1


def test_search_is_case_insensitive():
    analysis = an_analysis((an_entry(message="Disk Full"),))
    assert len(search(analysis, "disk full")) == 1


def test_search_ignores_a_word_inside_a_longer_word():
    analysis = an_analysis((an_entry(message="errors 0"),))
    assert search(analysis, "error") == []


def test_search_does_not_match_a_prefix():
    analysis = an_analysis((an_entry(message="category"),))
    assert search(analysis, "cat") == []


def test_search_reads_the_continuations():
    analysis = an_analysis((an_entry(message="boom",
                                     continuations=("PermissionError",)),))
    assert search(analysis, "PermissionError") == list(analysis.entries)


def test_search_does_not_look_at_the_level():
    analysis = an_analysis((an_entry(level="CRITICAL", message="disk full"),))
    assert search(analysis, "CRITICAL") == []


def test_search_refuses_an_empty_word():
    with pytest.raises(LogError, match="must not be empty"):
        search(an_analysis((an_entry(),)), "   ")


def test_search_refuses_a_word_that_is_not_text():
    with pytest.raises(LogError, match="must be text, got int"):
        search(an_analysis((an_entry(),)), 7)


def test_search_escapes_a_regex_character():
    analysis = an_analysis((an_entry(message="a.b"),))
    assert len(search(analysis, "a.b")) == 1
    assert search(an_analysis((an_entry(message="axb"),)), "a.b") == []


# --------------------------------------------------------------------------- #
# The legacy chain
# --------------------------------------------------------------------------- #
def test_legacy_counts_all_four_branches():
    lines = ["INFO a", "WARNING b", "ERROR c", "CRITICAL d"]
    assert legacy_counts(lines) == {"INFO": 1, "WARNING": 1, "ERROR": 1,
                                    "CRITICAL": 1}


def test_legacy_counts_a_line_it_cannot_name():
    assert legacy_counts(["nothing here"]) == {"UNKNOWN": 1}


def test_legacy_has_no_debug_branch():
    assert legacy_counts(["DEBUG a"]) == {"UNKNOWN": 1}


def test_legacy_calls_a_debug_line_with_informational_info():
    assert legacy_classify("2026-05-11 08:04:00 DEBUG Informational banner") \
        == "INFO"


def test_legacy_calls_errors_zero_an_error():
    assert legacy_classify("2026-05-11 08:07:00 DEBUG errors 0") == "ERROR"


def test_legacy_calls_a_critical_with_error_an_error():
    assert legacy_classify("2026-05-11 09:00:12 CRITICAL error in loop") == \
        "ERROR"


def test_legacy_calls_a_warning_with_info_info():
    assert legacy_classify("2026-05-11 08:08:00 WARNING User info record") == \
        "INFO"


def test_legacy_ignores_the_case_of_the_line():
    assert legacy_classify("info lowercase") == "INFO"


def test_the_legacy_constants_are_pinned():
    assert LEGACY_LINE == "upper = line.upper()"
    assert LEGACY_EXTENSIONS == 'SUPPORTED_EXTENSIONS = [".log", ".txt"]'
    assert 'if "INFO" in upper' in LEGACY_CHAIN


def test_legacy_lines_are_the_nonblank_lines():
    lines = legacy_lines(analyze())
    assert len(lines) == 28 and all(line.strip() for line in lines)


def test_legacy_unknowns_split_real_entries_from_junk():
    real, others = legacy_unknowns(analyze())
    assert len(real) == 2 and len(others) == 8
    assert all("DEBUG" in text for _, _, text in real)


def test_a_legacy_traceback_is_not_an_entry():
    _real, others = legacy_unknowns(analyze())
    texts = [text for _, _, text in others]
    assert "Traceback (most recent call last):" in texts
    assert any(text.startswith('  File "src/cache.py"') for text in texts)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def test_report_rows_hold_one_row_per_file_and_a_total():
    analysis = an_analysis((an_entry(),))
    rows = report_rows(analysis)
    assert len(rows) == 2 and rows[0][0] == "a.log" and rows[1][0] == "TOTAL"


def test_a_report_row_carries_all_five_levels():
    assert report_rows(an_analysis((an_entry(),)))[0] == \
        ["a.log", "1", "0", "1", "0", "0", "0", "0", "0"]


def test_report_text_starts_with_the_header():
    assert report_text(an_analysis((an_entry(),))).splitlines()[0] == \
        "File,Entries,DEBUG,INFO,WARNING,ERROR,CRITICAL,Continued,Malformed"


def test_report_text_ends_with_a_newline():
    assert report_text(an_analysis((an_entry(),))).endswith("\n")


def test_report_text_has_a_line_per_file_plus_header_and_total():
    assert len(report_text(an_analysis((an_entry(),))).splitlines()) == 3


# --------------------------------------------------------------------------- #
# The seeded logs
# --------------------------------------------------------------------------- #
def test_the_seeded_folder_is_the_bundled_one():
    assert LOGS.name == "logs" and LOGS.parent.name == "data"


def test_the_seeded_folder_holds_three_files():
    assert len(analyze().files) == 3


def test_the_seeded_bytes_are_pinned():
    assert analyze().blobs == 1460


def test_the_seeded_nonblank_lines_are_pinned():
    assert analyze().nonblank == 28


def test_the_seeded_entries_are_pinned():
    assert len(analyze()) == 18


def test_the_seeded_continuations_are_pinned():
    assert analyze().continuations == 6


def test_the_seeded_malformed_lines_are_pinned():
    assert len(analyze().bad) == 4


def test_the_seeded_level_counts_are_pinned():
    assert analyze().counts() == {"DEBUG": 4, "INFO": 7, "WARNING": 3,
                                  "ERROR": 3, "CRITICAL": 1}


def test_the_seeded_per_file_counts_are_pinned():
    counts = analyze().file_counts()
    assert counts["application.log"] == {"DEBUG": 3, "INFO": 4, "WARNING": 2,
                                         "ERROR": 2, "CRITICAL": 0}
    assert counts["worker.log"] == {"DEBUG": 1, "INFO": 3, "WARNING": 1,
                                    "ERROR": 1, "CRITICAL": 1}
    assert counts["notes.log"] == {level: 0 for level in LEVELS}


def test_the_seeded_malformed_line_numbers_are_pinned():
    assert [(line.file, line.line) for line in analyze().bad] == [
        ("application.log", 15), ("notes.log", 1), ("notes.log", 2),
        ("worker.log", 11)]


def test_the_seeded_span_is_pinned():
    first, last, seconds = analyze().span()
    assert first.strftime("%Y-%m-%d %H:%M:%S") == "2026-05-11 08:00:01"
    assert last.strftime("%Y-%m-%d %H:%M:%S") == "2026-05-11 09:00:13"
    assert seconds == 3612


def test_the_seeded_analysis_passes_every_check():
    assert analyze().problems() == []


def test_the_seeded_traceback_is_one_entry():
    traceback = next(entry for entry in analyze().entries
                     if entry.continuations)
    assert traceback.lines == 4 and traceback.level == "ERROR"
    assert traceback.file == "application.log" and traceback.line == 5


def test_the_seeded_embedded_timestamp_is_inside_a_message():
    entry = next(item for item in analyze().entries if "disk full" in item.message)
    assert entry.level == "INFO" and entry.lines == 1


def test_the_seeded_legacy_counts_are_pinned():
    counts = legacy_counts(legacy_lines(analyze()))
    assert counts == {"INFO": 9, "WARNING": 2, "ERROR": 7, "UNKNOWN": 10}
    # CRITICAL is absent from the counter, not zero-valued: no line ever
    # reached that branch, because the only critical line also says "error".
    assert "CRITICAL" not in counts and counts.get("CRITICAL", 0) == 0


def test_the_seeded_search_for_error_finds_three():
    assert len(search(analyze(), "error")) == 3


def test_the_seeded_search_for_errors_finds_one():
    hits = search(analyze(), "errors")
    assert len(hits) == 1 and hits[0].message == "Validation finished, errors 0"


def test_the_seeded_search_for_info_skips_informational():
    hits = search(analyze(), "info")
    assert len(hits) == 1 and hits[0].message == "User info record missing"


def test_the_seeded_report_has_five_lines():
    assert len(report_text(analyze()).splitlines()) == 5


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


def test_demo_shows_the_corpus(capsys):
    run_demo()
    assert "3 files, 1460 bytes, 28 non-blank lines" in capsys.readouterr().out


def test_demo_shows_a_zero_critical(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "application.log  11 entries" in out
    assert "CRITICAL 0" in out


def test_demo_shows_the_substring_misreadings(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "INFORMATIONAL contains INFO" in out
    assert "ERRORS contains ERROR" in out
    assert "the elif chain tests ERROR first" in out


def test_demo_shows_the_missing_debug_branch(capsys):
    run_demo()
    assert "no DEBUG branch at all" in capsys.readouterr().out


def test_demo_shows_the_traceback(capsys):
    run_demo()
    assert "occupies 4 lines: 1 entry, not 4" in capsys.readouterr().out


def test_demo_shows_the_legacy_totals(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "INFO       9" in out and "ERROR      7" in out
    assert "UNKNOWN   10" in out


def test_demo_shows_the_conservation_law(capsys):
    run_demo()
    assert "18 entries + 6 continuations + 4 malformed = 28 non-blank lines" \
        in capsys.readouterr().out


def test_demo_shows_the_span(capsys):
    run_demo()
    assert "3612 seconds" in capsys.readouterr().out


def test_demo_shows_the_word_search(capsys):
    run_demo()
    assert "search('error') finds 3 entries as whole words" in \
        capsys.readouterr().out


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


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


def test_cli_prints_the_summary_and_the_table(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "entries      18" in out
    assert "TOTAL                 18        4        7" in out


def test_cli_prints_the_span(capsys):
    assert cli.main([]) == 0
    assert "2026-05-11 08:00:01 to 2026-05-11 09:00:13 (3612 s)" in \
        capsys.readouterr().out


def test_cli_says_a_zero_is_a_measurement(capsys):
    assert cli.main(["--levels"]) == 0
    assert "a zero is a measurement" in capsys.readouterr().out


def test_cli_lists_the_malformed_lines(capsys):
    assert cli.main(["--malformed"]) == 0
    out = capsys.readouterr().out
    assert "application.log:15" in out and "4 malformed line(s)" in out
    assert "'---' is not a level" in out


def test_cli_malformed_says_nothing_when_clean(tmp_path, capsys):
    a_log(tmp_path, "a.log", "2026-05-11 08:00:01 INFO ok\n")
    assert cli.main(["--logs", str(tmp_path), "--malformed"]) == 0
    assert "every non-blank line parsed" in capsys.readouterr().out


def test_cli_search_lists_the_matches(capsys):
    assert cli.main(["--search", "error"]) == 0
    out = capsys.readouterr().out
    assert "3 entries whose message contains 'error'" in out
    assert "Health check passed, no error detected" in out


def test_cli_search_reports_no_match(tmp_path, capsys):
    a_log(tmp_path, "a.log", "2026-05-11 08:00:01 INFO ok\n")
    assert cli.main(["--logs", str(tmp_path), "--search", "missing"]) == 0
    assert "nothing matched" in capsys.readouterr().out


def test_cli_search_of_one_entry_uses_the_singular(tmp_path, capsys):
    a_log(tmp_path, "a.log", "2026-05-11 08:00:01 INFO only one\n")
    assert cli.main(["--logs", str(tmp_path), "--search", "only"]) == 0
    assert "1 entry whose message" in capsys.readouterr().out


def test_cli_legacy(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "no branch exists" in out
    assert "a real DEBUG entry the chain has no branch for" in out
    assert "the chain counted 28 lines as 28 entries" in out


def test_cli_report_writes_csv(tmp_path, capsys):
    target = tmp_path / "out.csv"
    assert cli.main(["--report", str(target)]) == 0
    capsys.readouterr()
    lines = target.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("File,Entries,DEBUG")
    assert lines[-1].startswith("TOTAL,18,4,7,3,3,1,6,4")


def test_cli_report_creates_directories(tmp_path, capsys):
    target = tmp_path / "a" / "b" / "out.csv"
    assert cli.main(["--report", str(target)]) == 0
    capsys.readouterr()
    assert target.is_file()


def test_cli_json_writes_the_analysis(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    import json
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["summary"]["entries"] == 18
    assert payload["summary"]["CRITICAL"] == 1
    assert len(payload["malformed"]) == 4
    assert payload["entries"][0]["level"] == "INFO"


def test_cli_json_is_ascii(tmp_path, capsys):
    target = tmp_path / "out.json"
    cli.main(["--json", str(target)])
    capsys.readouterr()
    assert all(ord(character) < 128
               for character in target.read_text(encoding="utf-8"))


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_quiet_still_searches(capsys):
    assert cli.main(["--search", "error", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_missing_folder_exits_two(capsys):
    assert cli.main(["--logs", "no-such-folder"]) == 2
    assert "folder not found" in capsys.readouterr().err


def test_cli_reads_another_folder(tmp_path, capsys):
    a_log(tmp_path, "a.log",
          "2026-05-11 08:00:01 INFO one\n2026-05-11 08:00:02 CRITICAL two\n")
    assert cli.main(["--logs", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "entries      2" in out and "CRITICAL 1" in out


def test_cli_handles_a_folder_with_an_empty_file(tmp_path, capsys):
    a_log(tmp_path, "empty.log", "")
    assert cli.main(["--logs", str(tmp_path)]) == 0
    assert "no entries, so no span" in capsys.readouterr().out
