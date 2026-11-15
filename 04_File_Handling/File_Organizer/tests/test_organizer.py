"""Tests for File_Organizer: compound suffixes, a plan, and a way back."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
from organizer import (                                       # noqa: E402
    CATEGORIES,
    COMPOUND,
    INBOX,
    LEGACY_COUNTER,
    LEGACY_SUFFIX,
    LEGACY_TABLE,
    OUT,
    SINGLE,
    FileEntry,
    Kind,
    Move,
    OrganizeError,
    Plan,
    apply_plan,
    build_plan,
    check_name,
    classify,
    folder_names,
    legacy_category,
    legacy_plan,
    naive_targets,
    run_demo,
    suffix_of,
    undo,
    unique_name,
)


def a_file(path: Path, text: str = "content\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def a_copy(tmp_path: Path) -> tuple[Path, Path]:
    """A copy of the bundled inbox and library, safe to move things in."""
    inbox = tmp_path / "inbox"
    out = tmp_path / "organized"
    shutil.copytree(INBOX, inbox)
    shutil.copytree(OUT, out)
    return inbox, out


def a_move(name: str = "notes.txt", category: str = "Documents",
           target_name: str | None = None, size: int = 5) -> Move:
    target_name = target_name or name
    return Move(Path("/inbox") / name, Path("/out") / category / target_name,
                category, size, "", name != target_name)


# --------------------------------------------------------------------------- #
# check_name
# --------------------------------------------------------------------------- #
def test_a_plain_name_is_accepted():
    assert check_name("notes.txt") == "notes.txt"


def test_an_empty_name_is_refused():
    with pytest.raises(OrganizeError, match="must not be empty"):
        check_name("   ")


def test_a_name_that_is_not_text_is_refused():
    with pytest.raises(OrganizeError, match="must be text, got int"):
        check_name(7)


def test_a_dot_is_not_a_file_name():
    with pytest.raises(OrganizeError, match="is a path"):
        check_name(".")


def test_a_double_dot_is_not_a_file_name():
    with pytest.raises(OrganizeError, match="is a path"):
        check_name("..")


def test_a_forward_slash_is_refused():
    with pytest.raises(OrganizeError, match="is a path"):
        check_name("a/b.txt")


def test_a_backslash_is_refused():
    with pytest.raises(OrganizeError, match="is a path"):
        check_name("a\\b.txt")


# --------------------------------------------------------------------------- #
# suffix_of / classify
# --------------------------------------------------------------------------- #
def test_a_simple_suffix_is_lower_cased():
    assert suffix_of("photo.JPG") == ".jpg"


def test_a_compound_suffix_beats_its_tail():
    assert suffix_of("archive.tar.gz") == ".tar.gz"


def test_a_compound_suffix_is_case_insensitive():
    assert suffix_of("BACKUP.TAR.GZ") == ".tar.gz"


def test_a_short_compound_suffix_is_known():
    assert suffix_of("bundle.tgz") == ".tgz"


def test_no_suffix_means_no_suffix():
    assert suffix_of("README") == ""


def test_a_name_that_is_only_an_extension_has_no_suffix():
    assert suffix_of(".txt") == ""


def test_an_unknown_tail_has_no_suffix():
    assert suffix_of("notes.txt.bak") == ""


def test_a_trailing_dot_has_no_suffix():
    assert suffix_of("notes.") == ""


def test_a_document_is_a_document():
    kind = classify("report.final.pdf")
    assert (kind.category, kind.suffix, kind.known) == \
        ("Documents", ".pdf", True)


def test_a_csv_is_data_not_others():
    assert classify("data.csv").category == "Data"


def test_markdown_is_a_document():
    assert classify("notes.md").category == "Documents"


def test_a_tar_archive_is_an_archive():
    assert classify("backup.tar.gz").category == "Archives"


def test_an_unknown_name_falls_back_to_others():
    kind = classify("README")
    assert (kind.category, kind.suffix, kind.known) == ("Others", "", False)


def test_a_kind_prints_its_suffix():
    assert str(Kind("Images", ".jpg", True)) == "Images (.jpg)"


def test_a_kind_prints_when_it_has_no_suffix():
    assert str(Kind("Others", "", False)) == "Others (no suffix)"


def test_a_kind_dict_holds_the_three_facts():
    assert classify("photo.PNG").to_dict() == {"category": "Images",
                                               "suffix": ".png",
                                               "known": True}


def test_the_folder_order_is_pinned():
    assert CATEGORIES == ("Images", "Documents", "Videos", "Music", "Archives",
                          "Data", "Python", "Others")


def test_the_compound_table_is_pinned():
    assert sorted(COMPOUND) == [".tar.bz2", ".tar.gz", ".tar.xz", ".tar.zst",
                                ".tbz2", ".tgz", ".txz"]


def test_every_compound_suffix_is_an_archive():
    assert set(COMPOUND.values()) == {"Archives"}


def test_the_single_table_names_every_folder_but_others():
    assert set(SINGLE) == set(CATEGORIES) - {"Others"}


def test_no_single_suffix_is_also_compound():
    singles = {suffix for suffixes in SINGLE.values() for suffix in suffixes}
    assert singles & set(COMPOUND) == set()


# --------------------------------------------------------------------------- #
# FileEntry
# --------------------------------------------------------------------------- #
def test_an_entry_keeps_its_name_and_size(tmp_path):
    entry = FileEntry(a_file(tmp_path / "notes.txt"), 8, classify("notes.txt"))
    assert entry.name == "notes.txt" and entry.size == 8


def test_an_entry_accepts_a_string_path(tmp_path):
    entry = FileEntry(str(a_file(tmp_path / "notes.txt")), 8,
                      classify("notes.txt"))
    assert isinstance(entry.path, Path)


def test_an_entry_refuses_a_negative_size():
    with pytest.raises(OrganizeError, match="negative size"):
        FileEntry(Path("notes.txt"), -1, classify("notes.txt"))


def test_an_entry_dict_holds_the_four_facts(tmp_path):
    payload = FileEntry(a_file(tmp_path / "data.csv"), 5,
                        classify("data.csv")).to_dict()
    assert payload == {"name": "data.csv", "size": 5, "category": "Data",
                       "suffix": ".csv"}


def test_an_entry_is_frozen(tmp_path):
    entry = FileEntry(a_file(tmp_path / "notes.txt"), 8, classify("notes.txt"))
    with pytest.raises(Exception):
        entry.size = 9                            # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Move
# --------------------------------------------------------------------------- #
def test_a_move_prints_as_an_arrow():
    assert str(a_move()) == "notes.txt -> Documents/notes.txt"


def test_a_move_dict_holds_both_paths():
    assert a_move("photo.JPG", "Images", "photo_1.JPG").to_dict() == {
        "from": "photo.JPG", "to": "Images/photo_1.JPG", "size": 5,
        "renamed": True}


def test_a_move_with_the_same_name_is_not_a_rename():
    assert a_move("notes.txt", "Documents", "notes.txt").renamed is False


def test_a_move_with_a_new_name_must_be_marked_a_rename():
    with pytest.raises(OrganizeError, match="is a rename"):
        Move(Path("photo.JPG"), Path("out/Images/photo_1.JPG"), "Images", 5,
             ".jpg", False)


def test_a_move_with_the_same_name_drops_a_wrong_rename_flag():
    move = Move(Path("notes.txt"), Path("out/Documents/notes.txt"),
                "Documents", 5, ".txt", True)
    assert move.renamed is False


def test_a_move_refuses_an_unknown_folder():
    with pytest.raises(OrganizeError, match="is not a folder"):
        a_move("notes.txt", "Spreadsheets")


def test_a_move_refuses_a_negative_size():
    with pytest.raises(OrganizeError, match="negative size"):
        Move(Path("a.txt"), Path("out/Documents/a.txt"), "Documents", -1,
             ".txt", False)


def test_a_move_accepts_string_paths():
    move = Move("a.txt", "out/Documents/a.txt", "Documents", 1, ".txt", False)
    assert isinstance(move.source, Path) and isinstance(move.target, Path)


# --------------------------------------------------------------------------- #
# unique_name
# --------------------------------------------------------------------------- #
def test_a_free_name_is_kept():
    assert unique_name("photo.JPG", ".jpg", set()) == ("photo.JPG", False)


def test_a_taken_name_gets_a_counter():
    assert unique_name("photo.JPG", ".jpg", {"photo.jpg"}) == \
        ("photo_1.JPG", True)


def test_the_counter_climbs_until_it_is_free():
    assert unique_name("photo.JPG", ".jpg", {"photo.jpg", "photo_1.jpg"}) == \
        ("photo_2.JPG", True)


def test_the_counter_goes_before_a_compound_suffix():
    assert unique_name("backup.tar.gz", ".tar.gz", {"backup.tar.gz"}) == \
        ("backup_1.tar.gz", True)


def test_the_counter_goes_after_a_name_with_no_suffix():
    assert unique_name("README", "", {"readme"}) == ("README_1", True)


def test_the_check_is_case_insensitive():
    # ``taken`` holds case-folded names, as folder_names returns them
    assert unique_name("PHOTO.JPG", ".jpg", {"photo.jpg"}) == \
        ("PHOTO_1.JPG", True)


def test_a_hidden_name_keeps_its_dot():
    assert unique_name(".gitignore", "", {".gitignore"}) == \
        (".gitignore_1", True)


def test_unique_name_does_not_touch_the_set():
    taken = {"photo.jpg"}
    unique_name("photo.JPG", ".jpg", taken)
    assert taken == {"photo.jpg"}


# --------------------------------------------------------------------------- #
# folder_names
# --------------------------------------------------------------------------- #
def test_folder_names_folds_the_case(tmp_path):
    a_file(tmp_path / "Photo.JPG")
    assert folder_names(tmp_path) == {"photo.jpg"}


def test_folder_names_of_a_missing_folder_is_empty(tmp_path):
    assert folder_names(tmp_path / "nope") == set()


def test_folder_names_lists_files_and_folders(tmp_path):
    a_file(tmp_path / "notes.txt")
    (tmp_path / "sub").mkdir()
    assert folder_names(tmp_path) == {"notes.txt", "sub"}


# --------------------------------------------------------------------------- #
# build_plan
# --------------------------------------------------------------------------- #
def test_a_plan_refuses_a_missing_inbox(tmp_path):
    with pytest.raises(OrganizeError, match="inbox not found"):
        build_plan(tmp_path / "nope", tmp_path / "out")


def test_a_plan_refuses_a_file_as_an_inbox(tmp_path):
    target = a_file(tmp_path / "a.txt")
    with pytest.raises(OrganizeError, match="is a file, not a folder"):
        build_plan(target, tmp_path / "out")


def test_an_empty_inbox_plans_nothing(tmp_path):
    (tmp_path / "inbox").mkdir()
    plan = build_plan(tmp_path / "inbox", tmp_path / "out")
    assert len(plan) == 0 and plan.summary()["bytes"] == 0


def test_a_plan_counts_its_moves(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt", "12345")
    a_file(inbox / "photo.jpg", "123")
    plan = build_plan(inbox, tmp_path / "out")
    assert len(plan) == 2 and plan.total_bytes == 8


def test_a_plan_reports_a_subfolder_and_leaves_it_alone(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    a_file(inbox / "later" / "old.txt")
    plan = build_plan(inbox, tmp_path / "out")
    assert len(plan) == 1 and [folder.name for folder in plan.folders] == \
        ["later"]


def test_a_plan_keeps_an_unknown_file_in_others(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "README")
    plan = build_plan(inbox, tmp_path / "out")
    assert plan.moves[0].category == "Others"


def test_a_plan_avoids_a_name_already_in_the_library(tmp_path):
    inbox, out = tmp_path / "inbox", tmp_path / "out"
    a_file(inbox / "notes.txt", "new")
    a_file(out / "Documents" / "notes.txt", "old")
    plan = build_plan(inbox, out)
    assert plan.moves[0].target.name == "notes_1.txt"
    assert plan.moves[0].renamed is True


def test_a_plan_reserves_names_it_hands_out(tmp_path):
    inbox, out = tmp_path / "inbox", tmp_path / "out"
    a_file(inbox / "photo.JPG", "a")
    a_file(inbox / "photo_1.JPG", "b")
    a_file(out / "Images" / "photo.JPG", "old")
    plan = build_plan(inbox, out)
    assert [move.target.name for move in plan.moves] == ["photo_1.JPG",
                                                         "photo_1_1.JPG"]


def test_a_plan_ignores_a_case_difference_in_the_library(tmp_path):
    inbox, out = tmp_path / "inbox", tmp_path / "out"
    a_file(inbox / "notes.txt", "new")
    a_file(out / "Documents" / "NOTES.TXT", "old")
    plan = build_plan(inbox, out)
    assert plan.moves[0].target.name == "notes_1.txt"


def test_a_plan_creates_no_folders(tmp_path):
    inbox, out = tmp_path / "inbox", tmp_path / "out"
    a_file(inbox / "track.mp3")
    build_plan(inbox, out)
    assert not out.exists()


def test_a_plan_groups_by_folder_in_folder_order(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "README")
    a_file(inbox / "track.mp3")
    a_file(inbox / "photo.jpg")
    plan = build_plan(inbox, tmp_path / "out")
    assert plan.categories() == ("Images", "Music", "Others")


def test_a_plan_orders_the_moves_by_name_within_a_folder(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "b.txt")
    a_file(inbox / "A.txt")
    plan = build_plan(inbox, tmp_path / "out")
    assert [move.source.name for move in plan] == ["A.txt", "b.txt"]


# --------------------------------------------------------------------------- #
# Plan protocol
# --------------------------------------------------------------------------- #
def test_a_plan_counts_its_moves_with_len(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    assert len(build_plan(inbox, tmp_path / "out")) == 1


def test_iteration_walks_the_moves(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    assert [move.category for move in build_plan(inbox, tmp_path / "out")] == \
        ["Documents"]


def test_a_plan_repr_counts_renames(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    plan = build_plan(inbox, tmp_path / "out")
    assert repr(plan) == "<Plan 1 moves, 8 bytes, 0 renamed>"


def test_renamed_lists_only_the_renames(tmp_path):
    inbox, out = tmp_path / "inbox", tmp_path / "out"
    a_file(inbox / "notes.txt")
    a_file(out / "Documents" / "notes.txt")
    plan = build_plan(inbox, out)
    assert len(plan.renamed) == 1


def test_by_category_skips_empty_folders(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    plan = build_plan(inbox, tmp_path / "out")
    assert list(plan.by_category()) == ["Documents"]


def test_the_summary_holds_every_count(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    summary = build_plan(inbox, tmp_path / "out").summary()
    assert summary == {"inbox": "inbox", "out": "out", "files": 1, "moves": 1,
                       "folders": 0, "categories": 1, "renamed": 0,
                       "bytes": 8}


def test_to_dict_holds_the_summary_moves_and_folders(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    payload = build_plan(inbox, tmp_path / "out").to_dict()
    assert set(payload) == {"summary", "moves", "folders"}


# --------------------------------------------------------------------------- #
# The audit
# --------------------------------------------------------------------------- #
def test_a_clean_plan_passes_every_check(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    plan = build_plan(inbox, tmp_path / "out")
    assert len(plan.audit()) == 7 and plan.problems() == []


def test_the_checks_are_named(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    assert [name for name, _ in build_plan(inbox, tmp_path / "out").audit()] == [
        "every source is a file in the inbox",
        "every target sits in its folder under the output root",
        "no two moves share a target",
        "no target is already on disk",
        "no source is used twice",
        "every move names one of the eight folders",
        "no move overwrites its own source"]


def test_the_audit_catches_a_missing_source(tmp_path):
    plan = build_plan(tmp_path, tmp_path / "out")
    gone = a_move("gone.txt")
    broken = Plan(tmp_path, tmp_path / "out", (), (), (gone,))
    assert "every source is a file in the inbox" in broken.problems()


def test_the_audit_catches_two_moves_with_one_target(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "a.txt")
    a_file(inbox / "b.txt")
    plan = build_plan(inbox, tmp_path / "out")
    second = Move(plan.moves[1].source, plan.moves[0].target,
                  plan.moves[1].category, plan.moves[1].size,
                  plan.moves[1].suffix, True)
    broken = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                  (plan.moves[0], second))
    assert broken.problems() == ["no two moves share a target"]


def test_the_audit_catches_a_target_that_is_taken(tmp_path):
    inbox, out = tmp_path / "inbox", tmp_path / "out"
    a_file(inbox / "notes.txt")
    a_file(out / "Documents" / "notes.txt", "older")
    plan = build_plan(inbox, out)
    occupied = Move(plan.moves[0].source, out / "Documents" / "notes.txt",
                    "Documents", plan.moves[0].size, ".txt", False)
    broken = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                  (occupied,))
    assert broken.problems() == ["no target is already on disk"]


def test_the_audit_catches_a_target_outside_the_library(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    plan = build_plan(inbox, tmp_path / "out")
    astray = Move(plan.moves[0].source, inbox / "Documents" / "notes.txt",
                  "Documents", plan.moves[0].size, ".txt", False)
    broken = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                  (astray,))
    assert broken.problems() == \
        ["every target sits in its folder under the output root"]


def test_the_audit_catches_a_source_used_twice(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    plan = build_plan(inbox, tmp_path / "out")
    first = plan.moves[0]
    second = Move(first.source, tmp_path / "out" / "Documents" / "other.txt",
                  "Documents", first.size, ".txt", True)
    broken = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                  (first, second))
    assert broken.problems() == ["no source is used twice"]


def test_the_audit_catches_an_unknown_folder(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    plan = build_plan(inbox, tmp_path / "out")
    move = plan.moves[0]
    object.__setattr__(move, "category", "Spreadsheets")
    broken = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                  (move,))
    assert "every move names one of the eight folders" in broken.problems()


def test_the_audit_catches_a_move_onto_its_own_source(tmp_path):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    plan = build_plan(inbox, tmp_path / "out")
    move = plan.moves[0]
    object.__setattr__(move, "target", move.source)
    broken = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                  (move,))
    assert "no move overwrites its own source" in broken.problems()


# --------------------------------------------------------------------------- #
# apply and undo
# --------------------------------------------------------------------------- #
def test_applying_a_plan_moves_every_file(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    applied = apply_plan(plan)
    assert len(applied) == 12
    assert [item.name for item in inbox.iterdir()] == ["later"]


def test_applying_a_plan_preserves_the_bytes(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    applied = apply_plan(plan)
    assert sum(move.target.stat().st_size for move in applied) == 629


def test_applying_a_plan_creates_the_folders_it_needs(tmp_path):
    inbox, out = a_copy(tmp_path)
    apply_plan(build_plan(inbox, out))
    assert (out / "Data").is_dir() and (out / "Others").is_dir()


def test_a_second_plan_after_applying_finds_nothing(tmp_path):
    inbox, out = a_copy(tmp_path)
    apply_plan(build_plan(inbox, out))
    assert len(build_plan(inbox, out)) == 0


def test_applying_a_plan_twice_does_nothing(tmp_path):
    inbox, out = a_copy(tmp_path)
    apply_plan(build_plan(inbox, out))
    assert apply_plan(build_plan(inbox, out)) == ()


def test_a_stale_plan_is_refused(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    target = plan.moves[0].target
    a_file(target, "someone else\n")
    with pytest.raises(OrganizeError, match="appeared after the plan"):
        apply_plan(plan)


def test_a_stale_plan_leaves_every_source_alone(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    a_file(plan.moves[0].target, "someone else\n")
    with pytest.raises(OrganizeError):
        apply_plan(plan)
    assert sum(1 for move in plan.moves if move.source.is_file()) == 12


def test_a_move_that_fails_half_way_is_rolled_back(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    a_file(plan.moves[2].target, "late arrival\n")
    with pytest.raises(OrganizeError):
        apply_plan(plan)
    assert sum(1 for move in plan.moves if move.source.is_file()) == 12
    assert not plan.moves[0].target.exists()
    assert not plan.moves[1].target.exists()


def test_a_vanished_source_is_refused(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    plan.moves[0].source.unlink()
    with pytest.raises(OrganizeError, match="is no longer there"):
        apply_plan(plan)


def test_undo_returns_every_file(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    undo(apply_plan(plan), out)
    names = {item.name for item in inbox.iterdir() if item.is_file()}
    assert names == {move.source.name for move in plan.moves}


def test_undo_restores_the_sizes(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    sizes = {move.source.name: move.size for move in plan.moves}
    undo(apply_plan(plan), out)
    assert {item.name: item.stat().st_size
            for item in inbox.iterdir() if item.is_file()} == sizes


def test_undo_removes_the_folders_it_created(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    undo(apply_plan(plan), out)
    left = sorted(folder.name for folder in out.iterdir())
    assert left == ["Archives", "Documents", "Images"]


def test_undo_is_itself_idempotent_after_unity(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    applied = apply_plan(plan)
    undo(applied, out)
    with pytest.raises(OrganizeError, match="is gone"):
        undo(applied, out)


def test_undo_refuses_when_the_source_is_back(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    applied = apply_plan(plan)
    a_file(plan.moves[0].source, "back again\n")
    with pytest.raises(OrganizeError, match="is back already"):
        undo(applied, out)


# --------------------------------------------------------------------------- #
# The legacy project
# --------------------------------------------------------------------------- #
def test_the_legacy_suffix_call_is_the_defect():
    assert LEGACY_SUFFIX == "extension = file_path.suffix.lower()"


def test_the_legacy_counter_line_is_the_defect():
    assert LEGACY_COUNTER == \
        'target = destination / f"{file.stem}_{counter}{file.suffix}"'


def test_the_legacy_table_is_pinned():
    assert LEGACY_TABLE["Others"] == []
    assert ".gz" not in LEGACY_TABLE["Archives"]


def test_legacy_calls_a_tar_gz_others():
    assert legacy_category("backup.tar.gz") == "Others"


def test_legacy_calls_a_csv_others():
    assert legacy_category("data.csv") == "Others"


def test_legacy_keeps_a_7z_an_archive():
    assert legacy_category("archive.7z") == "Archives"


def test_legacy_ignores_the_case_of_a_suffix():
    assert legacy_category("photo.JPG") == "Images"


def test_legacy_has_no_idea_about_a_file_without_a_suffix():
    assert legacy_category("README") == "Others"


def test_the_legacy_plan_misfiles_four_files():
    legacy = dict(legacy_plan())
    misfiled = [name for name, target in legacy.items()
                if target.split("/")[0] !=
                next(move.category for move in build_plan().moves
                     if move.source.name == name)]
    assert misfiled == ["backup.tar.gz", "data.csv", "notes.md",
                        "settings.json"]


def test_the_legacy_plan_puts_the_counter_inside_a_compound_name():
    assert dict(legacy_plan())["backup.tar.gz"] == "Others/backup.tar.gz"


def test_the_legacy_plan_renames_a_photo_twice(tmp_path):
    inbox, out = a_copy(tmp_path)
    legacy = dict(legacy_plan(inbox, out))
    assert legacy["photo.JPG"] == "Images/photo_1.JPG"
    assert legacy["photo_1.JPG"] == "Images/photo_1_1.JPG"


def test_a_plan_time_probe_repeats_a_target(tmp_path):
    inbox, out = a_copy(tmp_path)
    naive = naive_targets(build_plan(inbox, out))
    assert len(naive) == 12 and len(set(naive)) == 11
    assert naive.count("Images/photo_1.JPG") == 2


def test_a_plan_time_probe_splits_a_compound_name(tmp_path):
    inbox, out = a_copy(tmp_path)
    assert "Archives/backup.tar_1.gz" in naive_targets(build_plan(inbox, out))


def test_the_plan_has_no_repeated_target(tmp_path):
    inbox, out = a_copy(tmp_path)
    plan = build_plan(inbox, out)
    assert len({move.target for move in plan.moves}) == 12


# --------------------------------------------------------------------------- #
# The seeded folders
# --------------------------------------------------------------------------- #
def test_the_seeded_inbox_is_the_bundled_one():
    assert INBOX.name == "inbox" and INBOX.parent.name == "data"


def test_the_seeded_inbox_holds_twelve_files():
    assert sum(1 for item in INBOX.iterdir() if item.is_file()) == 12


def test_the_seeded_inbox_holds_one_subfolder():
    assert sum(1 for item in INBOX.iterdir() if item.is_dir()) == 1


def test_the_seeded_bytes_are_pinned():
    assert build_plan().total_bytes == 629


def test_the_seeded_plan_fills_seven_folders():
    assert build_plan().categories() == ("Images", "Documents", "Music",
                                         "Archives", "Data", "Python",
                                         "Others")


def test_the_seeded_plan_renames_four_files():
    assert [move.target.name for move in build_plan().renamed] == [
        "photo_1.JPG", "photo_1_1.JPG", "notes_1.txt", "backup_1.tar.gz"]


def test_the_seeded_plan_is_clean():
    assert build_plan().problems() == []


def test_the_seeded_library_is_untouched_by_planning():
    before = sorted(item.name for item in OUT.rglob("*"))
    build_plan()
    assert sorted(item.name for item in OUT.rglob("*")) == before


def test_the_seeded_inbox_is_untouched_by_planning():
    before = sorted(item.name for item in INBOX.rglob("*"))
    build_plan()
    assert sorted(item.name for item in INBOX.rglob("*")) == before


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


def test_demo_shows_the_inbox(capsys):
    run_demo()
    assert "12 files, 629 bytes" in capsys.readouterr().out


def test_demo_shows_the_compound_suffix(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "backup.tar.gz is Archives by .tar.gz" in out
    assert "which the legacy table maps to Others" in out


def test_demo_shows_the_four_renames(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "photo_1.JPG" in out and "backup_1.tar.gz" in out
    assert "notes_1.txt" in out


def test_demo_shows_the_repeated_target(capsys):
    run_demo()
    assert "Images/photo_1.JPG twice" in capsys.readouterr().out


def test_demo_shows_the_seven_checks(capsys):
    run_demo()
    assert "7/7 plan checks" in capsys.readouterr().out


def test_demo_shows_the_apply(capsys):
    run_demo()
    assert "applied 12 moves into a copy" in capsys.readouterr().out


def test_demo_shows_the_undo(capsys):
    run_demo()
    assert "undo returned all 12 files" in capsys.readouterr().out


def test_demo_shows_the_stale_refusal(capsys):
    run_demo()
    assert "stopped the run with 12/12 sources still in the inbox" in \
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


def test_cli_prints_a_plan_by_default(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "moves        12 in 7 folder(s)" in out
    assert "photo_1_1.JPG" in out


def test_cli_names_the_renamed_source(capsys):
    assert cli.main([]) == 0
    assert "(was backup.tar.gz)" in capsys.readouterr().out


def test_cli_reports_a_skipped_subfolder(capsys):
    assert cli.main([]) == 0
    assert "skipped 1 subfolder(s)" in capsys.readouterr().out


def test_cli_moves_nothing_by_default(capsys):
    before = sorted(item.name for item in INBOX.iterdir())
    cli.main([])
    capsys.readouterr()
    assert sorted(item.name for item in INBOX.iterdir()) == before


def test_cli_verify(capsys):
    assert cli.main(["--verify"]) == 0
    out = capsys.readouterr().out
    assert "PASS  no target is already on disk" in out
    assert "7/7 checks passed" in out


def test_cli_categories(capsys):
    assert cli.main(["--categories"]) == 0
    out = capsys.readouterr().out
    assert "Documents  .pdf .doc .docx .txt .md .odt .pptx .xlsx" in out
    assert "compound" in out


def test_cli_legacy(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "misplaces 4 of 12 file(s)" in out
    assert "backup.tar.gz, data.csv, notes.md, settings.json" in out


def test_cli_json_writes_the_plan(tmp_path, capsys):
    target = tmp_path / "plan.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["summary"]["moves"] == 12
    assert payload["moves"][0]["to"] == "Images/photo_1.JPG"
    assert payload["folders"] == ["later"]


def test_cli_json_is_ascii(tmp_path, capsys):
    target = tmp_path / "plan.json"
    cli.main(["--json", str(target)])
    capsys.readouterr()
    assert all(ord(character) < 128
               for character in target.read_text(encoding="utf-8"))


def test_cli_refuses_to_apply_the_bundled_folders(capsys):
    assert cli.main(["--apply"]) == 2
    assert "refusing to move the bundled folders" in capsys.readouterr().err


def test_cli_apply_needs_both_folders(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    a_file(inbox / "notes.txt")
    assert cli.main(["--apply", "--inbox", str(inbox)]) == 2
    assert "pass --inbox and --out" in capsys.readouterr().err


def test_cli_apply_moves_the_files(tmp_path, capsys):
    inbox, out = a_copy(tmp_path)
    assert cli.main(["--apply", "--inbox", str(inbox), "--out", str(out)]) == 0
    out_text = capsys.readouterr().out
    assert "12 file(s) moved, 629 bytes" in out_text
    assert (out / "Images" / "photo_1.JPG").is_file()


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_missing_inbox_exits_two(capsys):
    assert cli.main(["--inbox", "no-such-folder"]) == 2
    assert "inbox not found" in capsys.readouterr().err


def test_cli_plans_another_folder(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    a_file(inbox / "photo.JPG", "123")
    assert cli.main(["--inbox", str(inbox), "--out", str(tmp_path / "out")]) == 0
    assert "moves        1 in 1 folder(s)" in capsys.readouterr().out


def test_cli_says_nothing_to_do_for_an_empty_folder(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    assert cli.main(["--inbox", str(inbox), "--out", str(tmp_path / "out")]) == 0
    assert "nothing to do" in capsys.readouterr().out
