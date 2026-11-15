"""Tests for Folder_Backup_Tool: a count of paths is not a copy of a folder,
and a name from the clock is not a name that is free."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import backup as module                                    # noqa: E402
import main as cli                                            # noqa: E402
from backup import (                                         # noqa: E402
    AFTER_FILE,
    BACKUP_FILE,
    SHORT_DIGEST,
    TREE_FILE,
    BackupError,
    Difference,
    Entry,
    File,
    Plan,
    Session,
    Tree,
    Verdict,
    audit,
    build_session,
    check_path,
    copy_tree,
    count_only,
    damaged_after,
    digest_of,
    due,
    name_backups,
    next_name,
    parse_tree,
    plan,
    problems,
    read_tree,
    run_demo,
    verify,
    would_fire_early,
)

EMPTY_DIGEST = ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852"
                "b855")
ABC_DIGEST = ("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f2001"
              "5ad")

TREE_TEXT = "a.txt\tone\nb.txt\ttwo\nc.txt\tthree\n"


def a_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def bundled() -> Tree:
    return read_tree()


def damaged() -> Tree:
    return read_tree(BACKUP_FILE)


def after() -> Tree:
    return read_tree(AFTER_FILE)


def a_session() -> Session:
    """The session the demo audits: a real tree, one damaged file, a plan."""
    return build_session(bundled(), damaged_after(damaged(), after()),
                         after(), name_backups("docs", "20240101", 3))


def with_difference(verdict: Verdict, path: str, **changes) -> Verdict:
    differences = tuple(replace(entry, **changes) if entry.path == path
                        else entry for entry in verdict.differences)
    return replace(verdict, differences=differences)


# --------------------------------------------------------------------------- #
# A digest
# --------------------------------------------------------------------------- #
def test_a_digest_is_sixty_four_hex_characters():
    assert len(digest_of("one")) == 64
    assert all(character in "0123456789abcdef" for character in digest_of("one"))


def test_the_empty_text_has_a_known_digest():
    assert digest_of("") == EMPTY_DIGEST


def test_the_three_letter_word_has_a_known_digest():
    assert digest_of("abc") == ABC_DIGEST


def test_a_digest_is_the_same_every_time():
    assert digest_of("one") == digest_of("one")


def test_one_changed_letter_changes_the_digest():
    assert digest_of("one") != digest_of("One")


def test_a_digest_refuses_something_that_is_not_text():
    with pytest.raises(BackupError, match="holds text"):
        digest_of(b"one")


def test_the_printed_digest_is_the_first_eight_characters():
    assert digest_of("abc")[:SHORT_DIGEST] == "ba7816bf"


# --------------------------------------------------------------------------- #
# A path
# --------------------------------------------------------------------------- #
def test_a_plain_path_is_accepted():
    assert check_path("notes.txt") == "notes.txt"


def test_a_nested_path_is_accepted():
    assert check_path("src/deep/file.py") == "src/deep/file.py"


def test_a_backslash_is_refused():
    with pytest.raises(BackupError, match="forward slashes"):
        check_path("src\\file.py")


def test_an_absolute_path_is_refused():
    with pytest.raises(BackupError, match="relative"):
        check_path("/etc/passwd")


def test_a_blank_path_is_refused():
    with pytest.raises(BackupError, match="must be text"):
        check_path("   ")


def test_a_dot_segment_is_refused():
    with pytest.raises(BackupError, match="a dot"):
        check_path("./file.txt")


def test_a_double_dot_segment_is_refused():
    with pytest.raises(BackupError, match="a dot"):
        check_path("a/../b.txt")


def test_a_double_slash_is_refused():
    with pytest.raises(BackupError, match="a blank"):
        check_path("a//b.txt")


def test_a_control_character_is_refused():
    with pytest.raises(BackupError, match="control character"):
        check_path("a\tb.txt")


def test_a_path_that_is_not_text_is_refused():
    with pytest.raises(BackupError, match="must be text"):
        check_path(7)


# --------------------------------------------------------------------------- #
# A file, and what the manifest recorded
# --------------------------------------------------------------------------- #
def test_a_file_records_its_size():
    assert File("a.txt", "abc").size == 3


def test_a_file_records_its_digest():
    assert File("a.txt", "abc").digest == ABC_DIGEST


def test_a_file_prints_a_short_digest():
    assert File("a.txt", "abc").short() == "ba7816bf"


def test_a_size_is_measured_in_utf8_bytes():
    assert File("a.txt", "abc").size == 3


def test_an_empty_file_is_zero_bytes():
    assert File("a.txt", "").size == 0 and File("a.txt", "").digest == \
        EMPTY_DIGEST


def test_a_size_that_is_given_is_kept():
    """The record is stored, not recomputed, so an audit can disagree with it."""
    assert File("a.txt", "abc", 99).size == 99


def test_a_digest_that_is_given_is_kept():
    assert File("a.txt", "abc", 3, "0" * 64).digest == "0" * 64


def test_an_entry_prints_its_line():
    assert Entry("notes.txt", 11, "769ca1d1" + "0" * 56).line() == \
        "notes.txt          11 bytes  769ca1d1"


def test_an_entry_prints_a_short_digest():
    assert Entry("a.txt", 3, ABC_DIGEST).short() == "ba7816bf"


# --------------------------------------------------------------------------- #
# A tree
# --------------------------------------------------------------------------- #
def test_a_tree_knows_how_many_files_it_holds():
    assert len(parse_tree(TREE_TEXT)) == 3


def test_a_tree_looks_a_file_up_by_path():
    assert parse_tree(TREE_TEXT).get("b.txt").data == "two"


def test_a_tree_refuses_a_file_it_does_not_hold():
    with pytest.raises(BackupError, match="no file called 'ghost.txt'"):
        parse_tree(TREE_TEXT).get("ghost.txt")


def test_a_tree_indexes_its_files_by_path():
    assert sorted(parse_tree(TREE_TEXT).by_path()) == ["a.txt", "b.txt",
                                                       "c.txt"]


def test_a_tree_prints_one_line_per_file():
    lines = parse_tree(TREE_TEXT).lines()
    assert len(lines) == 3 and lines[0].startswith("a.txt ")


def test_the_manifest_is_sorted_by_path():
    tree = parse_tree("c.txt\tthree\na.txt\tone\n")
    assert [entry.path for entry in tree.manifest()] == ["a.txt", "c.txt"]


def test_a_tree_refuses_the_same_path_twice():
    with pytest.raises(BackupError, match="appears twice"):
        Tree((File("a.txt", "one"), File("a.txt", "two")))


def test_a_tree_refuses_a_bad_path():
    with pytest.raises(BackupError, match="relative"):
        Tree((File("/etc/passwd", "x"),))


def test_a_copy_is_a_new_value_with_the_same_record():
    original = bundled()
    duplicate = copy_tree(original)
    assert duplicate == original and duplicate is not original


def test_a_copy_can_be_damaged_without_touching_the_original():
    original = bundled()
    duplicate = copy_tree(original)
    assert duplicate.get("notes.txt") == original.get("notes.txt")


# --------------------------------------------------------------------------- #
# Reading a tree
# --------------------------------------------------------------------------- #
def test_a_tree_is_read_from_two_columns():
    tree = parse_tree("a.txt\tone\nb.txt\ttwo\n")
    assert tree.get("a.txt").data == "one"


def test_a_comment_line_is_skipped():
    assert len(parse_tree("; a note\n// another\na.txt\tone\n")) == 1


def test_a_blank_line_is_skipped():
    assert len(parse_tree("\n\na.txt\tone\n\n")) == 1


def test_a_tab_inside_the_text_is_kept():
    assert parse_tree("a.txt\tone\ttwo\n").get("a.txt").data == "one\ttwo"


def test_a_path_is_trimmed():
    assert parse_tree("  a.txt \tone\n").get("a.txt").data == "one"


def test_a_line_without_a_tab_is_refused():
    with pytest.raises(BackupError, match="line 1: expected a path"):
        parse_tree("a.txt one\n")


def test_a_bad_path_names_its_line():
    with pytest.raises(BackupError, match="line 2: a path uses forward"):
        parse_tree("a.txt\tone\nb\\c.txt\ttwo\n")


def test_a_tree_with_no_files_is_refused():
    with pytest.raises(BackupError, match="holds no files"):
        parse_tree("; nothing here\n")


def test_windows_line_endings_are_read():
    assert len(parse_tree(TREE_TEXT.replace("\n", "\r\n"))) == 3


def test_the_tree_is_sorted_however_it_was_written():
    tree = parse_tree("c.txt\tthree\na.txt\tone\nb.txt\ttwo\n")
    assert [entry.path for entry in tree.files] == ["a.txt", "b.txt", "c.txt"]


def test_read_tree_refuses_a_missing_file(tmp_path):
    with pytest.raises(BackupError, match="file not found"):
        read_tree(tmp_path / "nope.txt")


def test_the_bundled_tree_holds_five_files():
    assert len(bundled()) == 5


def test_the_bundled_paths_are_pinned():
    assert [entry.path for entry in bundled().files] == [
        "index.html", "notes.txt", "photo.jpg", "report.csv", "settings.ini"]


def test_the_bundled_sizes_are_pinned():
    assert [entry.size for entry in bundled().files] == [31, 11, 9, 8, 10]


# --------------------------------------------------------------------------- #
# Verifying
# --------------------------------------------------------------------------- #
def test_a_real_copy_verifies_clean():
    verdict = verify(bundled(), copy_tree(bundled()))
    assert verdict.ok() is True and verdict.differences == ()


def test_a_clean_verdict_counts_every_file_twice():
    verdict = verify(bundled(), copy_tree(bundled()))
    assert verdict.checked == 5 and verdict.identical == 5


def test_a_damaged_backup_does_not_verify():
    assert verify(bundled(), damaged()).ok() is False


def test_a_damaged_backup_names_the_file():
    differences = verify(bundled(), damaged()).differences
    assert len(differences) == 1 and differences[0].path == "photo.jpg"


def test_a_same_size_edit_is_a_digest_difference():
    difference = verify(bundled(), damaged()).differences[0]
    assert difference.kind == "digest"
    assert difference.detail == "the same 9 bytes, different content"


def test_a_shorter_file_is_a_size_difference():
    shorter = Tree(tuple(File(entry.path, "x" * 2) if entry.path == "notes.txt"
                         else entry for entry in bundled().files))
    difference = verify(bundled(), shorter).differences[0]
    assert difference.kind == "size"
    assert difference.detail == "11 bytes in the source, 2 in the backup"


def test_a_missing_file_is_named():
    smaller = Tree(tuple(entry for entry in bundled().files
                         if entry.path != "report.csv"))
    difference = verify(bundled(), smaller).differences[0]
    assert difference.kind == "missing"
    assert difference.path == "report.csv"


def test_an_extra_file_is_named():
    bigger = Tree(bundled().files + (File("stowaway.txt", "surprise"),))
    difference = verify(bundled(), bigger).differences[0]
    assert difference.kind == "extra"
    assert difference.path == "stowaway.txt"


def test_a_missing_file_is_not_reported_as_a_size_mismatch():
    """The order of the three tests is the lesson."""
    smaller = Tree(tuple(entry for entry in bundled().files
                         if entry.path != "notes.txt"))
    kinds = [entry.kind for entry in verify(bundled(), smaller).differences]
    assert kinds == ["missing"]


def test_a_verdict_counts_its_mismatches_and_its_extras():
    bigger = Tree(tuple(File(entry.path, "x" * 2) if entry.path == "notes.txt"
                        else entry for entry in bundled().files)
                  + (File("stowaway.txt", "surprise"),))
    verdict = verify(bundled(), bigger)
    assert verdict.counts() == (5, 4, 1, 1)


def test_a_verdict_with_an_extra_is_not_ok():
    bigger = Tree(bundled().files + (File("stowaway.txt", "surprise"),))
    assert verify(bundled(), bigger).ok() is False


def test_a_verdict_prints_its_summary():
    assert verify(bundled(), damaged()).summary() == \
        "5 file(s) checked, 4 identical, 1 different, 0 extra"


def test_a_verdict_prints_one_line_per_difference():
    assert verify(bundled(), damaged()).lines() == (
        "digest  photo.jpg       the same 9 bytes, different content",)


def test_a_verdict_needs_no_differences_to_be_ok():
    assert Verdict(0, 0).ok() is True


def test_verify_refuses_something_that_is_not_a_tree():
    with pytest.raises(BackupError, match="verify needs two trees"):
        verify(bundled(), "a folder")


# --------------------------------------------------------------------------- #
# The legacy count check
# --------------------------------------------------------------------------- #
def test_the_legacy_count_check_passes_a_damaged_backup():
    """The defect, executable: five paths beside five paths."""
    assert count_only(bundled(), damaged()) is True
    assert verify(bundled(), damaged()).ok() is False


def test_the_legacy_count_check_passes_a_folder_with_three_changes():
    assert len(after()) == len(bundled())
    assert count_only(after(), bundled()) is True


def test_the_legacy_count_check_fails_when_a_file_is_gone():
    smaller = Tree(tuple(entry for entry in bundled().files
                         if entry.path != "report.csv"))
    assert count_only(bundled(), smaller) is False


def test_the_legacy_count_check_is_fooled_by_a_swap():
    """Delete one file, add another: the count never moves."""
    swapped = Tree(tuple(entry for entry in bundled().files
                         if entry.path != "report.csv")
                   + (File("new.txt", "extra"),))
    assert count_only(bundled(), swapped) is True
    assert verify(bundled(), swapped).ok() is False


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
def test_a_plan_names_what_was_added():
    assert plan(after(), bundled()).added == ("draft.md",)


def test_a_plan_names_what_was_removed():
    assert plan(after(), bundled()).removed == ("settings.ini",)


def test_a_plan_names_what_changed():
    assert plan(after(), bundled()).changed == ("notes.txt",)


def test_a_plan_names_what_did_not():
    assert plan(after(), bundled()).unchanged == ("index.html", "photo.jpg",
                                                  "report.csv")


def test_a_plan_counts_its_four_lists():
    assert plan(after(), bundled()).counts() == (1, 1, 1, 3)


def test_a_plan_totals_every_path():
    assert plan(after(), bundled()).total() == 6


def test_a_plan_prints_its_summary():
    assert plan(after(), bundled()).summary() == \
        "1 added, 1 changed, 1 removed, 3 unchanged"


def test_a_plan_prints_one_line_per_path():
    assert plan(after(), bundled()).lines()[:3] == (
        "added     draft.md", "changed   notes.txt", "removed   settings.ini")


def test_a_same_size_edit_is_a_change():
    """Only a digest finds an edit that kept its size."""
    left = Tree((File("notes.txt", "alpha bravo"),))
    right = Tree((File("notes.txt", "alpha BRAVO"),))
    assert left.get("notes.txt").size == right.get("notes.txt").size
    assert plan(left, right).changed == ("notes.txt",)


def test_an_identical_tree_has_nothing_to_do():
    assert plan(bundled(), copy_tree(bundled())).counts() == (0, 0, 0, 5)


def test_two_empty_trees_have_nothing_to_do():
    assert plan(Tree(()), Tree(())).counts() == (0, 0, 0, 0)


def test_a_plan_against_an_empty_tree_adds_everything():
    assert plan(bundled(), Tree(())).counts() == (5, 0, 0, 0)


def test_a_plan_against_a_full_tree_removes_everything():
    assert plan(Tree(()), bundled()).counts() == (0, 0, 5, 0)


def test_a_plan_puts_every_path_in_exactly_one_list():
    step = plan(after(), bundled())
    assert len(step.paths()) == len(set(step.paths()))


def test_plan_refuses_something_that_is_not_a_tree():
    with pytest.raises(BackupError, match="plan needs two trees"):
        plan(bundled(), [1, 2, 3])


# --------------------------------------------------------------------------- #
# Naming a backup
# --------------------------------------------------------------------------- #
def test_a_free_name_is_the_name():
    assert next_name("docs") == "docs"


def test_a_taken_name_gets_a_number():
    assert next_name("docs", ["docs"]) == "docs-2"


def test_the_numbers_climb():
    assert next_name("docs", ["docs", "docs-2"]) == "docs-3"


def test_a_gap_in_the_numbers_is_not_reused():
    assert next_name("docs", ["docs", "docs-3"]) == "docs-2"


def test_a_name_is_compared_without_case():
    assert next_name("Docs", ["docs"]) == "Docs-2"


def test_a_name_is_trimmed():
    assert next_name("  docs  ") == "docs"


def test_a_blank_name_is_refused():
    with pytest.raises(BackupError, match="needs a name"):
        next_name("  ")


def test_a_name_with_a_separator_is_refused():
    with pytest.raises(BackupError, match="one folder name"):
        next_name("a/b")


def test_a_name_with_a_backslash_is_refused():
    with pytest.raises(BackupError, match="one folder name"):
        next_name("a\\b")


def test_three_backups_in_one_second_get_three_names():
    names = name_backups("docs", "20240101_120000", 3)
    assert names == ("docs_20240101_120000", "docs_20240101_120000-2",
                     "docs_20240101_120000-3")


def test_a_name_is_never_reused():
    names = name_backups("docs", "20240101_120000", 12)
    assert len(set(names)) == 12


# --------------------------------------------------------------------------- #
# Scheduling, without a clock
# --------------------------------------------------------------------------- #
def test_a_three_minute_window_has_three_ticks():
    assert due(0, 60, 180) == (60, 120, 180)


def test_a_tick_on_the_boundary_is_due():
    assert due(0, 60, 60) == (60,)


def test_a_window_that_closes_inside_the_first_interval_has_none():
    assert due(0, 60, 10) == ()


def test_an_interval_that_does_not_divide_the_window_stops_short():
    assert due(0, 60, 130) == (60, 120)


def test_a_window_of_zero_length_has_none():
    assert due(0, 60, 0) == ()


def test_a_zero_interval_is_refused():
    with pytest.raises(BackupError, match="interval is positive"):
        due(0, 0, 60)


def test_a_window_that_closes_before_it_opens_is_refused():
    with pytest.raises(BackupError, match="cannot close before it opens"):
        due(60, 60, 0)


def test_the_legacy_loop_fires_after_a_stop_arrives_mid_sleep():
    """The defect, executable: the flag is read before the sleep, not after."""
    assert would_fire_early(0, 60, 10) is True
    assert due(0, 60, 10) == ()


def test_a_stop_that_arrives_at_a_tick_does_not_fire_one_more():
    assert would_fire_early(0, 60, 60) is False


def test_a_stop_before_the_start_is_refused():
    with pytest.raises(BackupError, match="cannot arrive before the start"):
        would_fire_early(60, 60, 0)


# --------------------------------------------------------------------------- #
# A session
# --------------------------------------------------------------------------- #
def test_a_session_wires_the_verdict_and_the_plan():
    session = build_session(bundled(), damaged(), after(), ("docs",))
    assert session.verdict == verify(bundled(), damaged())
    assert session.plan == plan(bundled(), after())


def test_a_session_keeps_the_names():
    assert build_session(bundled(), damaged(), after(), ("docs",)).taken == \
        ("docs",)


def test_a_session_holds_the_damaged_file_in_place():
    """The demo's audit session keeps the corrupt bytes so it has one to name."""
    tree = damaged_after(damaged(), after())
    assert tree.get("photo.jpg").data == "JPEGDATA2"
    assert tree.get("notes.txt").data == "alpha bravo"


def test_the_demo_session_reports_every_kind_of_difference():
    verdict = a_session().verdict
    kinds = sorted((entry.path, entry.kind) for entry in verdict.differences)
    assert kinds == [("draft.md", "extra"), ("photo.jpg", "digest"),
                     ("settings.ini", "missing")]
    assert verdict.counts() == (5, 3, 2, 1)


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every digest is the digest of that file's own bytes",
    "every recorded size is the size of that file's own bytes",
    "every tree is sorted by path and holds no path twice",
    "the verdict names every file the backup is missing",
    "the verdict names every file the backup holds and the source does not",
    "a same-size edit is reported as a digest difference",
    "the verdict's counts add up, and ok means no difference at all",
    "the plan puts every path in exactly one of its four lists",
    "no two backups share a name, even case-insensitively",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_session())] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_session():
    assert problems(audit(a_session())) == []


def test_the_audit_is_repeatable():
    assert audit(a_session()) == audit(a_session())


def test_the_audit_catches_a_wrong_digest():
    session = a_session()
    wrong = replace(session.source.get("notes.txt"), digest="0" * 64)
    broken = replace(session, source=Tree(tuple(
        wrong if entry.path == "notes.txt" else entry
        for entry in session.source.files)))
    assert CHECK_NAMES[0] in problems(audit(broken))


def test_the_audit_catches_a_wrong_size():
    session = a_session()
    wrong = replace(session.source.get("notes.txt"), size=99)
    broken = replace(session, source=Tree(tuple(
        wrong if entry.path == "notes.txt" else entry
        for entry in session.source.files)))
    assert CHECK_NAMES[1] in problems(audit(broken))


def test_the_audit_does_not_raise_on_a_wrong_digest():
    session = a_session()
    wrong = replace(session.source.get("notes.txt"), digest="0" * 64)
    broken = replace(session, source=Tree(tuple(
        wrong if entry.path == "notes.txt" else entry
        for entry in session.source.files)))
    assert len(audit(broken)) == 9


def test_the_audit_catches_a_tree_that_is_not_sorted():
    session = a_session()
    broken = replace(session, previous=Tree(tuple(reversed(
        session.previous.files))))
    assert CHECK_NAMES[2] in problems(audit(broken))


def test_the_audit_catches_a_missing_file_it_forgot_to_name():
    session = a_session()
    quiet = tuple(entry for entry in session.verdict.differences
                  if entry.kind != "missing")
    broken = replace(session, verdict=replace(session.verdict,
                                              differences=quiet))
    assert CHECK_NAMES[3] in problems(audit(broken))


def test_the_audit_catches_an_extra_file_it_forgot_to_name():
    session = a_session()
    quiet = tuple(entry for entry in session.verdict.differences
                  if entry.kind != "extra")
    broken = replace(session, verdict=replace(session.verdict,
                                              differences=quiet))
    assert CHECK_NAMES[4] in problems(audit(broken))


def test_the_audit_catches_a_same_size_edit_called_something_else():
    session = a_session()
    broken = replace(session, verdict=with_difference(session.verdict,
                                                     "photo.jpg", kind="size"))
    assert CHECK_NAMES[5] in problems(audit(broken))


def test_the_audit_catches_a_verdict_whose_counts_do_not_add_up():
    session = a_session()
    broken = replace(session, verdict=replace(session.verdict,
                                              identical=0))
    assert CHECK_NAMES[6] in problems(audit(broken))


def test_the_audit_catches_a_plan_with_a_path_twice():
    session = a_session()
    doubled = replace(session.plan,
                      added=session.plan.added + (session.plan.changed[0],))
    broken = replace(session, plan=doubled)
    assert CHECK_NAMES[7] in problems(audit(broken))


def test_the_audit_catches_two_names_that_differ_only_in_case():
    session = a_session()
    broken = replace(session, taken=(session.taken[0], session.taken[0].upper()))
    assert CHECK_NAMES[8] in problems(audit(broken))


def test_a_difference_prints_its_line():
    assert Difference("photo.jpg", "digest", "the same 9 bytes").line() == \
        "digest  photo.jpg       the same 9 bytes"


def test_a_plan_with_no_lists_counts_nothing():
    assert Plan().counts() == (0, 0, 0, 0)


# --------------------------------------------------------------------------- #
# The legacy lines
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert module.LEGACY_VERIFY == "return len(source_files) == " \
                                   "len(backup_files)"
    assert module.LEGACY_MERGE == \
        "shutil.copytree(source, backup_folder, dirs_exist_ok=True)"
    assert module.LEGACY_LOOP == ("while self.running:\n    time.sleep(interval)"
                                  "\n    callback()")


def test_the_three_bundled_files_are_pinned_on_disk():
    assert TREE_FILE.read_text(encoding="utf-8").count("\t") == 5
    assert BACKUP_FILE.read_text(encoding="utf-8").count("\t") == 5
    assert AFTER_FILE.read_text(encoding="utf-8").count("\t") == 5


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


def test_demo_shows_the_count_check_passing_a_damaged_backup(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "return len(source_files) == len(backup_files)" in out
    assert "so the legacy check answers True -- a corrupted backup passes" in out


def test_demo_shows_the_digest_difference(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "photo.jpg           9 bytes  c0744a0a" in out
    assert "photo.jpg           9 bytes  a7d76c82" in out
    assert "digest  photo.jpg       the same 9 bytes, different content" in out


def test_demo_shows_that_a_real_copy_is_clean(capsys):
    run_demo()
    assert "5 file(s) checked, 5 identical, 0 different, 0 extra -> True" in \
        capsys.readouterr().out


def test_demo_shows_three_names_for_one_second(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "docs_20240101_120000-3" in out
    assert "three backups, three names, no merge: True" in out


def test_demo_shows_the_same_size_edit(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "'notes.txt' kept its size and changed its text" in out
    assert "the legacy count still says True: 5 path(s) then, 5 now" in out


def test_demo_shows_the_stop_that_is_too_late(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "already sleeping, so the callback still runs: True" in out
    assert "a window 0 to 10 has ticks ()" in out
    assert "a window 0 to 180 has ticks (60, 120, 180)" in out


def test_demo_shows_all_nine_checks(capsys):
    run_demo()
    assert "9/9 checks pass" in capsys.readouterr().out


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


def test_cli_prints_the_verdict_and_the_plan(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "  5 file(s) in the source, 5 in the backup, 5 in the previous" in out
    assert "  the legacy count check says True" in out
    assert "digest  photo.jpg       the same 9 bytes, different content" in out
    assert "  the backup is what it claims to be: False" in out
    assert "added     settings.ini" in out and "removed   draft.md" in out


def test_cli_prints_the_first_free_name(capsys):
    assert cli.main(["--name", "docs", "--taken", "docs,docs-2"]) == 0
    assert "the first free name for 'docs' is 'docs-3'" in \
        capsys.readouterr().out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_json(tmp_path, capsys):
    target = tmp_path / "session.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["legacy_count_passes"] is True
    assert payload["verify"]["ok"] is False
    assert payload["verify"]["mismatches"] == 1
    assert payload["verify"]["differences"][0]["path"] == "photo.jpg"
    assert payload["plan"]["added"] == ["settings.ini"]
    assert len(payload["source"]) == 5


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_reads_another_source_and_backup(tmp_path, capsys):
    source = a_file(tmp_path / "source.txt", "a.txt\tone\nb.txt\ttwo\n")
    backup = a_file(tmp_path / "backup.txt", "a.txt\tone\nb.txt\tTWO\n")
    assert cli.main(["--source", str(source), "--backup", str(backup)]) == 0
    out = capsys.readouterr().out
    assert "  2 file(s) in the source, 2 in the backup, 2 in the previous" in out
    assert "  the backup is what it claims to be: False" in out
    assert "the same 3 bytes, different content" in out


def test_cli_a_missing_file_exits_two(tmp_path, capsys):
    assert cli.main(["--source", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_line_exits_two(tmp_path, capsys):
    path = a_file(tmp_path / "tree.txt", "no tab here\n")
    assert cli.main(["--source", str(path)]) == 2
    assert "expected a path, a tab" in capsys.readouterr().err


def test_cli_a_bad_name_exits_two(capsys):
    assert cli.main(["--name", "a/b"]) == 2
    assert "one folder name" in capsys.readouterr().err
