"""Tests for Bulk_File_Renamer: a batch rename is a plan that must cover the
folder, because `zip` truncates and a computed name can land on a file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
import renamer as module                                      # noqa: E402
from renamer import (                                         # noqa: E402
    FOLDER_FILE,
    LEGACY_HISTORY,
    LEGACY_LOOP,
    LEGACY_TARGET,
    MAX_NAME,
    NAMES_FILE,
    RESERVED,
    TRIES,
    Applied,
    BadName,
    DiskFolder,
    Entry,
    MemoryFolder,
    PlanError,
    RenameError,
    UndoError,
    Workbook,
    apply,
    audit,
    build_plan,
    check_name,
    fold,
    numbered,
    problems,
    read_folder,
    read_lines,
    run_demo,
    split_name,
    target_for,
    undo,
)

STARTING = ("notes.txt", "photo.JPG", "report.pdf", "scan.pdf", "summary.txt",
            "todo.md")
EXPECTED = {"notes.txt": "chapter-one.txt", "photo.JPG": "photo-2024.JPG",
            "report.pdf": "q3-report.pdf", "scan.pdf": "invoice.pdf",
            "summary.txt": "final-summary.txt", "todo.md": "checklist.md"}


def a_file(folder: Path, text: str, name: str = "names.txt") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


def bundled() -> MemoryFolder:
    return read_folder()


def names() -> tuple[str, ...]:
    return read_lines()


# --------------------------------------------------------------------------- #
# Names
# --------------------------------------------------------------------------- #
def test_split_name_separates_a_stem_and_a_suffix():
    assert split_name("report.pdf") == ("report", ".pdf")


def test_split_name_keeps_the_last_dot():
    assert split_name("backup.tar.gz") == ("backup.tar", ".gz")


def test_split_name_of_a_bare_name_has_no_suffix():
    assert split_name("notes") == ("notes", "")


def test_split_name_keeps_a_dotfile_whole():
    assert split_name(".env") == (".env", "")


def test_split_name_refuses_text_that_is_not_a_name():
    with pytest.raises(BadName, match="a name must be text"):
        split_name(7)


def test_fold_ignores_case():
    assert fold("Photo.JPG") == fold("photo.jpg")


def test_a_plain_name_is_accepted():
    assert check_name("chapter-one") == "chapter-one"


def test_a_name_with_a_suffix_is_accepted():
    assert check_name("q3-report.pdf") == "q3-report.pdf"


def test_an_empty_name_is_refused():
    with pytest.raises(BadName, match="a name cannot be empty"):
        check_name("   ")


def test_a_name_with_a_leading_space_is_refused():
    with pytest.raises(BadName, match="cannot start or end with a space"):
        check_name(" notes.txt")


def test_a_dot_dot_is_not_a_name():
    with pytest.raises(BadName, match="is not a file name"):
        check_name("..")


def test_a_name_with_a_path_separator_is_refused():
    with pytest.raises(BadName, match="a name cannot hold"):
        check_name("sub/notes.txt")


def test_a_name_with_a_colon_is_refused():
    with pytest.raises(BadName, match="a name cannot hold"):
        check_name("C:notes")


def test_a_name_ending_in_a_dot_is_refused():
    with pytest.raises(BadName, match="cannot end with a dot"):
        check_name("notes.")


def test_a_name_longer_than_the_limit_is_refused():
    with pytest.raises(BadName, match=f"at most {MAX_NAME} characters"):
        check_name("x" * (MAX_NAME + 1))


def test_a_reserved_name_is_refused():
    with pytest.raises(BadName, match="is a name Windows reserves"):
        check_name("CON.txt")
    assert "con" in RESERVED


def test_a_control_character_is_refused():
    with pytest.raises(BadName, match="control character"):
        check_name("no\ttabs")


def test_a_bare_name_takes_the_old_suffix():
    assert target_for("chapter-one", "notes.txt") == "chapter-one.txt"


def test_a_name_with_its_own_suffix_is_used_whole():
    assert target_for("q3-report.pdf", "notes.txt") == "q3-report.pdf"


def test_the_old_suffix_is_not_added_twice():
    assert target_for("report.pdf", "scan.pdf") == "report.pdf"


def test_numbered_keeps_the_suffix_last():
    assert numbered("report.pdf", 2) == "report-2.pdf"


def test_numbered_works_on_a_bare_name():
    assert numbered("notes", 1) == "notes-1"


# --------------------------------------------------------------------------- #
# The folder
# --------------------------------------------------------------------------- #
def test_the_bundled_folder_holds_six_files():
    assert bundled().names() == STARTING


def test_a_memory_folder_round_trips_its_contents():
    folder = MemoryFolder({"a.txt": "one"})
    assert folder.read("a.txt") == "one" and len(folder) == 1


def test_a_memory_folder_refuses_a_name_that_differs_only_in_case():
    folder = MemoryFolder({"a.txt": "one", "b.txt": "two"})
    with pytest.raises(RenameError, match="already there"):
        folder.move("a.txt", "B.TXT")


def test_a_move_to_an_occupied_name_is_refused():
    folder = MemoryFolder({"a.txt": "one", "b.txt": "two"})
    with pytest.raises(RenameError, match="already there"):
        folder.move("a.txt", "b.txt")


def test_a_move_of_a_missing_file_is_refused():
    with pytest.raises(RenameError, match="no such file"):
        MemoryFolder({"a.txt": "one"}).move("b.txt", "c.txt")


def test_a_move_reaches_a_name_that_differs_only_in_case():
    folder = MemoryFolder({"photo.JPG": "data"})
    folder.move("photo.JPG", "photo.jpg")
    assert folder.names() == ("photo.jpg",) and folder.read("photo.jpg") == "data"


def test_a_disk_folder_lists_only_files(tmp_path):
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    assert DiskFolder(tmp_path).names() == ("a.txt",)


def test_a_disk_folder_moves_a_file(tmp_path):
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    DiskFolder(tmp_path).move("a.txt", "b.txt")
    assert (tmp_path / "b.txt").is_file() and not (tmp_path / "a.txt").exists()


def test_a_disk_folder_refuses_to_overwrite(tmp_path):
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    (tmp_path / "b.txt").write_text("two", encoding="utf-8")
    with pytest.raises(RenameError, match="already there"):
        DiskFolder(tmp_path).move("a.txt", "b.txt")


def test_a_disk_folder_makes_a_case_only_rename_in_two_steps(tmp_path):
    (tmp_path / "photo.JPG").write_text("data", encoding="utf-8")
    DiskFolder(tmp_path).move("photo.JPG", "photo.jpg")
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["photo.jpg"]


def test_a_disk_folder_needs_a_folder(tmp_path):
    with pytest.raises(RenameError, match="not a folder"):
        DiskFolder(tmp_path / "nope")


# --------------------------------------------------------------------------- #
# The plan
# --------------------------------------------------------------------------- #
def test_the_bundled_plan_has_six_entries():
    assert len(build_plan(bundled(), names())) == 6


def test_the_bundled_plan_is_pinned():
    assert {entry.old: entry.new for entry in build_plan(bundled(), names())} == \
        EXPECTED


def test_the_bundled_plan_needs_no_notes():
    assert build_plan(bundled(), names()).notes() == ()


def test_every_entry_keeps_a_suffix():
    assert all(split_name(entry.new)[1] for entry in
               build_plan(bundled(), names()))


def test_a_short_list_is_refused():
    with pytest.raises(PlanError, match=r"names 4 file\(s\) but the folder "
                                       r"holds 6"):
        build_plan(bundled(), names()[:4])


def test_a_long_list_is_refused():
    with pytest.raises(PlanError, match=r"names 7 file\(s\) but the folder "
                                       r"holds 6"):
        build_plan(bundled(), list(names()) + ["extra"])


def test_a_repeated_target_is_refused():
    with pytest.raises(PlanError, match="two files would both be called "
                                       "'invoice.pdf'"):
        build_plan(bundled(), list(names()[:-1]) + ["invoice.pdf"])


def test_names_that_are_not_a_list_are_refused():
    with pytest.raises(PlanError, match="the names must be a list"):
        build_plan(bundled(), set(names()))


def test_a_file_named_twice_in_the_order_is_refused():
    with pytest.raises(PlanError, match="the plan lists a file twice"):
        build_plan(bundled(), names(), ordered=["notes.txt", "notes.txt"])


def test_a_file_the_folder_does_not_hold_is_refused():
    with pytest.raises(PlanError, match="holds no file called 'ghost.txt'"):
        build_plan(bundled(), names(), ordered=["ghost.txt"])


def test_an_order_that_leaves_a_file_out_is_refused():
    with pytest.raises(PlanError, match=r"leaves out 5 file\(s\)"):
        build_plan(bundled(), names(), ordered=["notes.txt"])


def test_a_collision_with_a_staying_file_is_numbered():
    folder = MemoryFolder({"keep.txt": "the original", "move.txt": "the mover"})
    plan = build_plan(folder, ["keep", "keep.txt"])
    assert plan.entries[0].new == "keep.txt"
    assert plan.entries[1].new == "keep-1.txt"


def test_a_numbered_entry_says_why():
    folder = MemoryFolder({"keep.txt": "the original", "move.txt": "the mover"})
    assert "renamed to avoid 'keep.txt'" in plan_note(folder)


def plan_note(folder):
    return build_plan(folder, ["keep", "keep.txt"]).entries[1].note


def test_a_numbered_entry_keeps_the_name_that_was_asked_for():
    folder = MemoryFolder({"keep.txt": "the original", "move.txt": "the mover"})
    entry = build_plan(folder, ["keep", "keep.txt"]).entries[1]
    assert entry.wanted == "keep.txt" and entry.new == "keep-1.txt"


def test_a_case_only_rename_is_noted():
    folder = MemoryFolder({"photo.JPG": "data"})
    entry = build_plan(folder, ["photo.jpg"]).entries[0]
    assert entry.new == "photo.jpg" and "case-only" in entry.note


def test_a_file_that_keeps_its_name_is_not_counted_as_changed():
    folder = MemoryFolder({"a.txt": "one", "b.txt": "two"})
    plan = build_plan(folder, ["a", "b"])
    assert plan.changed() == ()


def test_an_entry_prints_its_note_in_brackets():
    assert str(Entry("a.txt", "b.txt", "b.txt", "why")) == \
        "a.txt -> b.txt  (why)"


def test_an_entry_without_a_note_prints_only_the_move():
    assert str(Entry("a.txt", "b.txt", "b.txt")) == "a.txt -> b.txt"


def test_a_plan_iterates_over_its_entries():
    assert [entry.old for entry in build_plan(bundled(), names())] == \
        list(STARTING)


# --------------------------------------------------------------------------- #
# Applying and undoing
# --------------------------------------------------------------------------- #
def test_apply_renames_every_file():
    folder = bundled()
    apply(folder, build_plan(folder, names()))
    assert folder.names() == tuple(sorted(EXPECTED.values()))


def test_apply_keeps_the_contents():
    folder = bundled()
    apply(folder, build_plan(folder, names()))
    assert folder.read("chapter-one.txt") == "week one notes"


def test_apply_returns_one_record_per_change():
    folder = bundled()
    records = apply(folder, build_plan(folder, names()))
    assert len(records) == 6 and records[0] == Applied("notes.txt",
                                                       "chapter-one.txt")


def test_apply_refuses_a_plan_for_a_folder_that_moved_on():
    folder = bundled()
    plan = build_plan(folder, names())
    folder.move("notes.txt", "moved.txt")
    with pytest.raises(PlanError, match="not in the folder any more"):
        apply(folder, plan)


def test_apply_refuses_a_target_that_appeared_after_the_plan():
    folder = bundled()
    plan = build_plan(folder, names())
    folder.move("todo.md", "chapter-one.txt")
    with pytest.raises(PlanError, match="appeared in the folder"):
        apply(folder, plan)


def test_apply_needs_a_plan():
    with pytest.raises(PlanError, match="apply needs a Plan"):
        apply(bundled(), [("a", "b")])


def test_undo_restores_every_name():
    folder = bundled()
    records = apply(folder, build_plan(folder, names()))
    undo(folder, records)
    assert folder.names() == STARTING


def test_undo_returns_the_records_in_reverse():
    folder = bundled()
    records = apply(folder, build_plan(folder, names()))
    back = undo(folder, records)
    assert back[0] == Applied("checklist.md", "todo.md")


def test_undo_of_nothing_is_refused():
    with pytest.raises(UndoError, match="there is nothing to undo"):
        undo(bundled(), ())


def test_undo_refuses_a_file_that_is_not_where_the_rename_left_it():
    folder = bundled()
    records = apply(folder, build_plan(folder, names()))
    folder.move("checklist.md", "elsewhere.md")
    with pytest.raises(UndoError, match="is not where the rename left it"):
        undo(folder, records)


def test_a_second_batch_keeps_the_first_batch_s_history():
    """The legacy `history.clear()` lost the undo of the previous batch."""
    folder = MemoryFolder({"a.txt": "1", "b.txt": "2"})
    book = Workbook(folder)
    book.apply(book.plan(["one", "two"]))
    assert len(book.records) == 2
    book.apply(book.plan(["three", "two"]))
    assert len(book.records) == 3
    book.undo()
    assert folder.names() == ("a.txt", "b.txt")


def test_the_workbook_undoes_the_last_n_records():
    folder = MemoryFolder({"a.txt": "1", "b.txt": "2", "c.txt": "3"})
    book = Workbook(folder)
    book.apply(book.plan(["x", "y", "z"]))
    book.undo(2)
    assert folder.names() == ("b.txt", "c.txt", "x.txt")


def test_the_workbook_counts_the_plans_it_built():
    book = Workbook(MemoryFolder({"a.txt": "1"}))
    book.plan(["b"])
    assert book.plans_built == 1


def test_the_workbook_refuses_an_undo_it_cannot_pay_for():
    book = Workbook(MemoryFolder({"a.txt": "1"}))
    book.apply(book.plan(["b"]))
    with pytest.raises(UndoError, match=r"cannot undo 5"):
        book.undo(5)


def test_the_workbook_refuses_an_undo_of_nothing():
    with pytest.raises(UndoError, match="there is nothing to undo"):
        Workbook(MemoryFolder({"a.txt": "1"})).undo()


def test_the_workbook_says_whether_it_has_history():
    book = Workbook(MemoryFolder({"a.txt": "1"}))
    assert not book.has_history()
    book.apply(book.plan(["b"]))
    assert book.has_history()


# --------------------------------------------------------------------------- #
# The data files
# --------------------------------------------------------------------------- #
def test_read_lines_refuses_a_missing_file(tmp_path):
    with pytest.raises(PlanError, match="file not found"):
        read_lines(tmp_path / "nope.txt")


def test_read_lines_skips_comments_and_blanks(tmp_path):
    path = a_file(tmp_path, "; head\n\nalpha\n// note\nbeta\n")
    assert read_lines(path) == ("alpha", "beta")


def test_read_lines_refuses_a_name_that_is_too_long(tmp_path):
    with pytest.raises(PlanError, match="at most 60 characters"):
        read_lines(a_file(tmp_path, "x" * 61 + "\n"))


def test_the_bundled_name_list_holds_six_names():
    assert len(names()) == 6


def test_read_folder_builds_the_contents(tmp_path):
    path = a_file(tmp_path, "a.txt\tone\nb.txt\ttwo\n", "folder.txt")
    assert read_folder(path).read("b.txt") == "two"


def test_read_folder_refuses_a_missing_file(tmp_path):
    with pytest.raises(PlanError, match="folder file not found"):
        read_folder(tmp_path / "nope.txt")


def test_read_folder_refuses_a_file_with_no_names(tmp_path):
    with pytest.raises(PlanError, match="no files"):
        read_folder(a_file(tmp_path, "; nothing\n", "folder.txt"))


def test_read_folder_refuses_a_name_twice(tmp_path):
    with pytest.raises(PlanError, match="appears twice"):
        read_folder(a_file(tmp_path, "a.txt\tone\nA.txt\ttwo\n", "folder.txt"))


def test_read_folder_names_the_bad_line(tmp_path):
    with pytest.raises(PlanError, match="folder.txt:2:"):
        read_folder(a_file(tmp_path, "a.txt\tone\nb/c.txt\ttwo\n", "folder.txt"))


def test_the_bundled_files_are_pinned_on_disk():
    assert FOLDER_FILE.read_text(encoding="utf-8").count("\n") == 7
    assert NAMES_FILE.read_text(encoding="utf-8").count("\n") == 8


# --------------------------------------------------------------------------- #
# The legacy lines
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert LEGACY_LOOP == "for old_path, new_name in zip(files, new_names):"
    assert LEGACY_TARGET == \
        "new_file = old_file.with_name(new_name + old_file.suffix)"
    assert LEGACY_HISTORY == "self.history.clear()"


def test_zip_truncates_the_bundled_pairing():
    assert len(list(zip(bundled().names(), names()[:4]))) == 4


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(bundled(), build_plan(bundled(),
                                                            names()))] == [
        "the plan names exactly the files the folder holds",
        "no two files share a name, even case-insensitively",
        "no two entries want the same target name",
        "every new name is legal on Windows and on POSIX",
        "no entry points at a file that stays where it is",
        "no file loses its suffix",
        "the records name the files the plan moved",
        "every entry that departs from the asked-for name says why",
        "the plan lists each file exactly once"]


def test_the_audit_passes_on_the_bundled_plan():
    folder = bundled()
    assert problems(audit(folder, build_plan(folder, names()))) == []


def test_the_audit_passes_after_apply_and_undo():
    before = bundled()
    folder = bundled()
    records = apply(folder, build_plan(folder, names()))
    assert problems(audit(before, build_plan(before, names()), records)) == []
    undo(folder, records)


def test_the_audit_catches_a_plan_that_leaves_a_file_out():
    before = bundled()
    plan = build_plan(before, names())
    trimmed = type(plan)(plan.entries[:-1])
    assert "the plan names exactly the files the folder holds" in \
        problems(audit(before, trimmed))


def test_the_audit_catches_a_repeated_target():
    before = bundled()
    plan = build_plan(before, names())
    doubled = type(plan)(plan.entries[:1] + (Entry("todo.md", "chapter-one.txt",
                                                  "chapter-one.txt"),) +
                         plan.entries[2:])
    assert "no two entries want the same target name" in \
        problems(audit(before, doubled))


def test_the_audit_catches_an_illegal_name():
    before = bundled()
    plan = build_plan(before, names())
    broken = type(plan)(plan.entries[:1] + (Entry("todo.md", "a/b.txt",
                                                 "a/b.txt"),) +
                        plan.entries[2:])
    assert "every new name is legal on Windows and on POSIX" in \
        problems(audit(before, broken))


def test_the_audit_catches_an_entry_that_overwrites_a_staying_file():
    folder = MemoryFolder({"keep.txt": "1", "move.txt": "2"})
    plan = build_plan(folder, ["keep", "keep.txt"])
    broken = type(plan)((Entry("keep.txt", "keep.txt", "keep.txt"),
                         Entry("move.txt", "keep.txt", "keep.txt")))
    assert "no entry points at a file that stays where it is" in \
        problems(audit(folder, broken))


def test_the_audit_catches_a_file_that_loses_its_suffix():
    folder = MemoryFolder({"a.txt": "1", "b.gif": "2"})
    plan = type(build_plan(folder, ["a", "b"]))(
        (Entry("a.txt", "a", "a"), Entry("b.gif", "b", "b")))
    assert "no file loses its suffix" in problems(audit(folder, plan))


def test_the_audit_catches_records_that_do_not_match_the_plan():
    folder = bundled()
    plan = build_plan(folder, names())
    records = (Applied("notes.txt", "notes.txt"),)
    assert "the records name the files the plan moved" in \
        problems(audit(folder, plan, records))


def test_the_audit_catches_an_unexplained_departure():
    folder = bundled()
    plan = build_plan(folder, names())
    broken = type(plan)(plan.entries[:1] + (Entry("todo.md", "checklist.md",
                                                 "checklist-9.md"),) +
                        plan.entries[2:])
    assert "every entry that departs from the asked-for name says why" in \
        problems(audit(folder, broken))


def test_the_audit_catches_a_plan_that_names_a_file_twice():
    folder = bundled()
    plan = build_plan(folder, names())
    doubled = type(plan)(plan.entries[:1] + plan.entries[:1] +
                         plan.entries[2:])
    assert "the plan lists each file exactly once" in problems(audit(folder,
                                                                     doubled))


def test_the_audit_is_repeatable():
    folder = bundled()
    assert audit(folder, build_plan(folder, names())) == \
        audit(folder, build_plan(folder, names()))


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


def test_demo_shows_the_folder_and_the_short_list(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "    notes.txt           week one notes" in out
    assert "zip() pairs 4 of the 6 files and returns 4" in out


def test_demo_shows_the_plan_and_the_undo(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "    notes.txt -> chapter-one.txt" in out
    assert "applied 6 rename(s); the folder is now:" in out
    assert "every name is back: yes" in out


def test_demo_shows_the_numbered_collision(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "move.txt -> keep-1.txt  (renamed to avoid 'keep.txt', which is " \
           "already there)" in out
    assert "keep.txt still holds 'the original'" in out


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


def test_cli_prints_the_plan(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "  data/folder.txt: 6 files, 6 names" in out
    assert "    notes.txt -> chapter-one.txt" in out


def test_cli_apply_lists_the_new_names(capsys):
    assert cli.main(["--apply"]) == 0
    out = capsys.readouterr().out
    assert "  applied 6 rename(s); the folder now holds:" in out
    assert "    chapter-one.txt" in out
    assert "  6 record(s) kept, so undo needs 6" in out


def test_cli_undo_puts_the_names_back(capsys):
    assert cli.main(["--apply", "--undo", "2"]) == 0
    out = capsys.readouterr().out
    assert "    notes.txt" in out and "    summary.txt" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_a_short_list_exits_two(capsys):
    assert cli.main(["--short", "4"]) == 2
    assert "the plan names 4 file(s) but the folder holds 6" in \
        capsys.readouterr().err


def test_cli_json_writes_the_plan(tmp_path, capsys):
    target = tmp_path / "plan.json"
    assert cli.main(["--apply", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["names"] == list(names())
    assert payload["plan"][0]["new"] == "chapter-one.txt"
    assert len(payload["applied"]) == 6
    assert payload["notes"] == []


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_reads_another_folder_and_name_list(tmp_path, capsys):
    folder = a_file(tmp_path, "a.txt\tone\nb.txt\ttwo\n", "folder.txt")
    names_file = a_file(tmp_path, "alpha\nbeta\n", "names.txt")
    assert cli.main(["--folder", str(folder), "--names", str(names_file)]) == 0
    out = capsys.readouterr().out
    assert "folder.txt: 2 files, 2 names" in out
    assert "    a.txt -> alpha.txt" in out


def test_cli_a_missing_folder_exits_two(tmp_path, capsys):
    assert cli.main(["--folder", str(tmp_path / "nope.txt")]) == 2
    assert "folder file not found" in capsys.readouterr().err
