"""Tests for File_Synchronization_Tool: size, timestamp, digest, deletion."""

from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
from sync import (                                            # noqa: E402
    ACTIONS,
    COPY,
    DELETE,
    DESTINATION,
    LEGACY_ALWAYS,
    LEGACY_NEVER_DELETES,
    ORPHAN,
    SKIP,
    SOURCE,
    UPDATE,
    Change,
    FileState,
    Plan,
    SyncError,
    apply_plan,
    build_plan,
    digest,
    legacy_mirror,
    naive_mtime_plan,
    naive_size_plan,
    problems,
    run_demo,
    scan_tree,
    state,
    verify_mirror,
)


def a_file(path: Path, text: str = "text\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def a_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Two folders, safe to copy into and delete from."""
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()
    return source, dest


def a_copy(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    shutil.copytree(SOURCE, source)
    shutil.copytree(DESTINATION, dest)
    return source, dest


# --------------------------------------------------------------------------- #
# digest / state
# --------------------------------------------------------------------------- #
def test_digest_is_the_sha256_of_the_bytes(tmp_path):
    import hashlib
    target = a_file(tmp_path / "a.txt", "hello\n")
    assert digest(target) == hashlib.sha256(b"hello\n").hexdigest()


def test_digest_reads_in_chunks(tmp_path):
    target = a_file(tmp_path / "a.txt", "x" * 5000)
    assert digest(target, chunk=3) == digest(target)


def test_digest_of_an_empty_file_is_known(tmp_path):
    assert digest(a_file(tmp_path / "empty.txt", "")).startswith("e3b0c442")


def test_digest_refuses_a_missing_file(tmp_path):
    with pytest.raises(SyncError, match="not a file"):
        digest(tmp_path / "nope.txt")


def test_digest_refuses_a_directory(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(SyncError, match="not a file"):
        digest(folder)


def test_state_reads_the_size_and_the_timestamp(tmp_path):
    target = a_file(tmp_path / "a.txt", "12345")
    reading = state(target)
    assert reading.size == 5 and reading.mtime_ns == target.stat().st_mtime_ns


def test_state_refuses_a_missing_file(tmp_path):
    with pytest.raises(SyncError, match="not a file"):
        state(tmp_path / "nope.txt")


def test_a_file_state_refuses_a_negative_size(tmp_path):
    with pytest.raises(SyncError, match="negative size"):
        FileState(tmp_path / "a.txt", -1, 0)


def test_a_file_state_accepts_a_string_path(tmp_path):
    assert isinstance(FileState("a.txt", 0, 0).path, Path)


def test_a_file_state_dict_names_the_file(tmp_path):
    payload = state(a_file(tmp_path / "a.txt", "12345")).to_dict()
    assert payload["path"] == "a.txt" and payload["size"] == 5


# --------------------------------------------------------------------------- #
# scan_tree
# --------------------------------------------------------------------------- #
def test_scan_tree_refuses_a_missing_folder(tmp_path):
    with pytest.raises(SyncError, match="folder not found"):
        scan_tree(tmp_path / "nope")


def test_scan_tree_refuses_a_file(tmp_path):
    target = a_file(tmp_path / "a.txt")
    with pytest.raises(SyncError, match="is a file, not a folder"):
        scan_tree(target)


def test_scan_tree_of_an_empty_folder_is_empty(tmp_path):
    assert scan_tree(tmp_path) == {}


def test_scan_tree_keys_are_relative_forward_slashes(tmp_path):
    a_file(tmp_path / "deep" / "nested" / "a.txt")
    assert list(scan_tree(tmp_path)) == ["deep/nested/a.txt"]


def test_scan_tree_ignores_directories(tmp_path):
    a_file(tmp_path / "a.txt")
    (tmp_path / "empty").mkdir()
    assert list(scan_tree(tmp_path)) == ["a.txt"]


def test_scan_tree_orders_by_name(tmp_path):
    a_file(tmp_path / "b.txt")
    a_file(tmp_path / "A.txt")
    assert list(scan_tree(tmp_path)) == ["A.txt", "b.txt"]


def test_scan_tree_holds_a_state_per_file(tmp_path):
    a_file(tmp_path / "a.txt", "12345")
    assert scan_tree(tmp_path)["a.txt"].size == 5


# --------------------------------------------------------------------------- #
# Change
# --------------------------------------------------------------------------- #
def test_a_change_names_its_action_and_reason():
    change = Change(COPY, "a.txt", 5, None, "not in the destination")
    assert change.action == COPY and change.path == "a.txt"
    assert str(change) == "copy   a.txt  (not in the destination)"


def test_a_change_refuses_an_unknown_action():
    with pytest.raises(SyncError, match="is not an action"):
        Change("move", "a.txt", 1, None, "made up")


def test_a_change_refuses_a_negative_size():
    with pytest.raises(SyncError, match="negative size"):
        Change(COPY, "a.txt", -1, None, "made up")


def test_a_change_refuses_a_negative_other_size():
    with pytest.raises(SyncError, match="negative size"):
        Change(ORPHAN, "a.txt", 0, -1, "made up")


def test_a_change_needs_a_path():
    with pytest.raises(SyncError, match="needs a path"):
        Change(COPY, "", 1, None, "made up")


def test_only_copy_update_and_delete_write():
    assert Change(COPY, "a", 1, None, "x").writes is True
    assert Change(UPDATE, "a", 1, 1, "x").writes is True
    assert Change(DELETE, "a", 0, 1, "x").writes is True
    assert Change(SKIP, "a", 1, 1, "x").writes is False
    assert Change(ORPHAN, "a", 0, 1, "x").writes is False


def test_a_change_bytes_is_the_source_size_for_a_copy():
    assert Change(COPY, "a", 5, None, "x").bytes == 5


def test_a_change_bytes_is_the_orphan_size_for_an_orphan():
    assert Change(ORPHAN, "a", 0, 7, "x").bytes == 7


def test_a_change_dict_holds_every_field():
    payload = Change(UPDATE, "a.txt", 5, 6, "size 5 vs 6").to_dict()
    assert payload == {"action": "update", "path": "a.txt", "size": 5,
                       "other_size": 6, "reason": "size 5 vs 6"}


def test_a_change_is_frozen():
    change = Change(COPY, "a", 1, None, "x")
    with pytest.raises(Exception):
        change.action = SKIP                        # type: ignore[misc]


def test_the_five_actions_are_pinned():
    assert ACTIONS == ("copy", "update", "skip", "delete", "orphan")


# --------------------------------------------------------------------------- #
# build_plan
# --------------------------------------------------------------------------- #
def test_a_plan_copies_a_missing_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "12345")
    plan = build_plan(source, dest)
    assert len(plan) == 1
    assert plan.changes[0].action == COPY
    assert plan.changes[0].reason == "not in the destination"


def test_a_plan_skips_an_identical_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "same\n")
    a_file(dest / "a.txt", "same\n")
    assert build_plan(source, dest).changes[0].action == SKIP


def test_a_plan_updates_when_the_sizes_differ(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "longer\n")
    a_file(dest / "a.txt", "short\n")
    change = build_plan(source, dest).changes[0]
    assert change.action == UPDATE and change.reason == "size 7 vs 6"


def test_a_plan_updates_when_the_bytes_differ_at_one_size(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "aaaaa")
    a_file(dest / "a.txt", "bbbbb")
    change = build_plan(source, dest).changes[0]
    assert change.action == UPDATE
    assert change.reason == "same size, different bytes"


def test_a_plan_reports_an_orphan(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "old.txt", "stale\n")
    change = build_plan(source, dest).changes[0]
    assert change.action == ORPHAN and change.bytes == 6


def test_a_plan_deletes_only_when_asked(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "old.txt", "stale\n")
    assert build_plan(source, dest, delete=True).changes[0].action == DELETE


def test_a_plan_with_a_missing_destination_copies_everything(tmp_path):
    source = tmp_path / "source"
    a_file(source / "a.txt", "12345")
    plan = build_plan(source, tmp_path / "not-yet-there")
    assert plan.counts()[COPY] == 1


def test_a_plan_of_two_empty_folders_is_empty(tmp_path):
    source, dest = a_pair(tmp_path)
    assert len(build_plan(source, dest)) == 0


def test_a_plan_refuses_a_destination_inside_the_source(tmp_path):
    source = tmp_path / "source"
    a_file(source / "a.txt")
    with pytest.raises(SyncError, match="destination is inside the source"):
        build_plan(source, source / "mirror")


def test_a_plan_refuses_a_source_inside_the_destination(tmp_path):
    dest = tmp_path / "dest"
    a_file(dest / "source" / "a.txt")
    with pytest.raises(SyncError, match="source is inside the destination"):
        build_plan(dest / "source", dest)


def test_a_plan_counts_one_read_for_a_missing_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "12345")
    assert build_plan(source, dest).hashes == 1


def test_a_plan_counts_one_read_when_the_sizes_differ(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "longer\n")
    a_file(dest / "a.txt", "short\n")
    assert build_plan(source, dest).hashes == 1


def test_a_plan_counts_two_reads_when_the_sizes_agree(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "same\n")
    a_file(dest / "a.txt", "same\n")
    assert build_plan(source, dest).hashes == 2


def test_a_plan_reaches_into_subfolders(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "deep" / "nested" / "a.txt")
    assert list(build_plan(source, dest).changes)[0].path == \
        "deep/nested/a.txt"


def test_a_plan_is_the_same_twice(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "same\n")
    a_file(dest / "a.txt", "same\n")
    assert build_plan(source, dest).to_dict() == \
        build_plan(source, dest).to_dict()


# --------------------------------------------------------------------------- #
# Plan protocol
# --------------------------------------------------------------------------- #
def a_plan(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "new.txt", "abc")
    a_file(source / "same.txt", "same\n")
    a_file(dest / "same.txt", "same\n")
    a_file(dest / "old.txt", "stale\n")
    return build_plan(source, dest)


def test_a_plan_counts_its_changes(tmp_path):
    assert len(a_plan(tmp_path)) == 3


def test_iteration_walks_every_change(tmp_path):
    # sorted by relative path: new.txt, old.txt, same.txt
    assert [change.action for change in a_plan(tmp_path)] == \
        [COPY, ORPHAN, SKIP]


def test_a_plan_repr_names_the_counts(tmp_path):
    assert repr(a_plan(tmp_path)) == ("<Plan 3 changes: 1 copy, 0 update, "
                                      "1 skip, 0 delete, 1 orphan>")


def test_counts_has_an_entry_for_every_action(tmp_path):
    assert a_plan(tmp_path).counts() == {COPY: 1, UPDATE: 0, SKIP: 1,
                                         DELETE: 0, ORPHAN: 1}


def test_by_action_skips_the_empty_actions(tmp_path):
    assert list(a_plan(tmp_path).by_action()) == [COPY, SKIP, ORPHAN]


def test_to_copy_holds_copies_and_updates(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "new.txt", "abc")
    a_file(source / "old.txt", "longer\n")
    a_file(dest / "old.txt", "x\n")
    assert len(build_plan(source, dest).to_copy) == 2


def test_bytes_to_copy_sums_the_sources(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "abc")
    a_file(source / "b.txt", "12345")
    assert build_plan(source, dest).bytes_to_copy == 8


def test_orphans_holds_both_the_deletes_and_the_orphans(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "a.txt", "x")
    assert len(build_plan(source, dest).orphans) == 1
    assert len(build_plan(source, dest, delete=True).orphans) == 1


def test_the_summary_holds_every_count(tmp_path):
    summary = a_plan(tmp_path).summary()
    assert summary == {"source": "source", "dest": "dest", "changes": 3,
                       "copy": 1, "update": 0, "skip": 1, "delete": 0,
                       "orphan": 1, "bytes_to_copy": 3, "bytes_to_delete": 6,
                       "hashes": 3}


def test_to_dict_holds_the_summary_and_the_changes(tmp_path):
    payload = a_plan(tmp_path).to_dict()
    assert set(payload) == {"summary", "changes"}
    assert len(payload["changes"]) == 3


# --------------------------------------------------------------------------- #
# The audit
# --------------------------------------------------------------------------- #
def test_a_clean_plan_passes_every_check(tmp_path):
    plan = a_plan(tmp_path)
    assert len(plan.audit()) == 6 and plan.problems() == []


def test_the_checks_are_named(tmp_path):
    assert [name for name, _ in a_plan(tmp_path).audit()] == [
        "every path is relative and climbs nowhere",
        "no two changes share a path",
        "every copy, update or skip has a source file",
        "every delete or orphan is only in the destination",
        "a delete is planned only when deletion is allowed",
        "no change reaches outside the destination"]


def test_the_audit_catches_a_climbing_path(tmp_path):
    source, dest = a_pair(tmp_path)
    plan = Plan(source, dest, (Change(COPY, "../escape.txt", 1, None, "x"),), 0)
    assert "every path is relative and climbs nowhere" in plan.problems()


def test_the_audit_catches_an_absolute_path(tmp_path):
    source, dest = a_pair(tmp_path)
    plan = Plan(source, dest, (Change(COPY, "/etc/passwd", 1, None, "x"),), 0)
    assert "every path is relative and climbs nowhere" in plan.problems()


def test_the_audit_catches_a_repeated_path(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "abc")
    plan = Plan(source, dest, (Change(COPY, "a.txt", 3, None, "x"),
                               Change(SKIP, "a.txt", 3, 3, "y")), 0)
    assert plan.problems() == ["no two changes share a path"]


def test_the_audit_catches_a_copy_with_no_source(tmp_path):
    source, dest = a_pair(tmp_path)
    plan = Plan(source, dest, (Change(COPY, "ghost.txt", 1, None, "x"),), 0)
    assert plan.problems() == ["every copy, update or skip has a source file"]


def test_the_audit_catches_an_orphan_that_is_in_the_source(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    plan = Plan(source, dest, (Change(ORPHAN, "a.txt", 0, 1, "x"),), 0)
    assert plan.problems() == \
        ["every delete or orphan is only in the destination"]


def test_the_audit_catches_a_delete_without_permission(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "old.txt", "stale\n")
    plan = build_plan(source, dest)
    forged = Plan(source, dest,
                  (Change(DELETE, "old.txt", 0, 6, "x"),), 0)
    assert forged.problems() == \
        ["a delete is planned only when deletion is allowed"]
    assert plan.problems() == []


def test_the_audit_accepts_a_delete_plan(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "old.txt", "stale\n")
    assert build_plan(source, dest, delete=True).problems() == []


# --------------------------------------------------------------------------- #
# apply_plan
# --------------------------------------------------------------------------- #
def test_applying_a_plan_copies_the_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "12345")
    apply_plan(build_plan(source, dest))
    assert (dest / "a.txt").read_text(encoding="utf-8") == "12345"


def test_applying_a_plan_creates_the_folders(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "deep" / "nested" / "a.txt")
    apply_plan(build_plan(source, dest))
    assert (dest / "deep" / "nested" / "a.txt").is_file()


def test_applying_a_plan_overwrites_an_old_copy(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "new\n")
    a_file(dest / "a.txt", "old\n")
    apply_plan(build_plan(source, dest))
    assert (dest / "a.txt").read_text(encoding="utf-8") == "new\n"


def test_applying_a_plan_leaves_no_temporary_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "12345")
    apply_plan(build_plan(source, dest))
    assert list(dest.rglob("*.syncing")) == []


def test_applying_a_plan_returns_what_it_did(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "12345")
    assert len(apply_plan(build_plan(source, dest))) == 1


def test_applying_a_delete_removes_the_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "old.txt", "stale\n")
    apply_plan(build_plan(source, dest, delete=True))
    assert not (dest / "old.txt").exists()


def test_applying_a_delete_prunes_the_empty_folder(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "old" / "deep" / "stale.txt", "x")
    apply_plan(build_plan(source, dest, delete=True))
    assert not (dest / "old").exists()


def test_a_mirror_is_complete_after_applying(tmp_path):
    source, dest = a_copy(tmp_path)
    apply_plan(build_plan(source, dest, delete=True))
    assert problems(source, dest) == []


def test_a_second_plan_after_applying_finds_only_skips(tmp_path):
    source, dest = a_copy(tmp_path)
    apply_plan(build_plan(source, dest, delete=True))
    again = build_plan(source, dest, delete=True)
    assert again.counts()[SKIP] == 9
    assert len(again.to_copy) == 0 and again.counts()[DELETE] == 0


def test_applying_an_unchanged_tree_does_nothing(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "same\n")
    a_file(dest / "a.txt", "same\n")
    assert apply_plan(build_plan(source, dest)) == ()


def test_a_copy_that_cannot_be_made_is_refused(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "12345")
    plan = build_plan(source, dest)
    (source / "a.txt").unlink()
    with pytest.raises(SyncError, match="cannot copy"):
        apply_plan(plan)


def test_a_delete_of_a_vanished_file_is_refused(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "old.txt", "stale\n")
    plan = build_plan(source, dest, delete=True)
    (dest / "old.txt").unlink()
    with pytest.raises(SyncError, match="no longer there to delete"):
        apply_plan(plan)


# --------------------------------------------------------------------------- #
# verify_mirror
# --------------------------------------------------------------------------- #
def test_verify_returns_three_checks(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    assert len(verify_mirror(source, dest)) == 3


def test_verify_names_its_checks(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    assert [name for name, _ in verify_mirror(source, dest)] == [
        "every source file is present in the destination",
        "every source file has the same bytes in the destination",
        "the destination holds no extra files"]


def test_verify_passes_a_true_mirror(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    a_file(dest / "a.txt", "x")
    assert all(ok for _, ok in verify_mirror(source, dest))


def test_verify_catches_a_missing_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    assert [ok for _, ok in verify_mirror(source, dest)] == [False, False, True]


def test_verify_catches_different_bytes(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    a_file(dest / "a.txt", "y")
    assert [ok for _, ok in verify_mirror(source, dest)] == [True, False, True]


def test_verify_catches_an_extra_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(dest / "stray.txt", "x")
    assert [ok for _, ok in verify_mirror(source, dest)] == [True, True, False]


def test_verify_handles_a_missing_destination(tmp_path):
    source = tmp_path / "source"
    a_file(source / "a.txt", "x")
    assert [ok for _, ok in verify_mirror(source, tmp_path / "nope")] == \
        [False, False, True]


# --------------------------------------------------------------------------- #
# The legacy project and the two shortcuts
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_the_defects():
    assert LEGACY_ALWAYS == ("return calculate_hash(source) != "
                             "calculate_hash(destination)")
    assert LEGACY_NEVER_DELETES == "FILES IN DESTINATION NOT IN SOURCE ARE LEFT ALONE"


def test_legacy_copies_what_differs(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    assert legacy_mirror(source, dest).copied == ("a.txt",)


def test_legacy_lists_what_matches(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    a_file(dest / "a.txt", "x")
    assert legacy_mirror(source, dest).already == ("a.txt",)


def test_legacy_hashes_both_sides_of_a_pair(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    a_file(dest / "a.txt", "x")
    assert legacy_mirror(source, dest).hashes == 2


def test_legacy_hashes_only_the_source_of_a_missing_file(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    assert legacy_mirror(source, dest).hashes == 1


def test_legacy_never_notices_an_orphan(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    a_file(dest / "stale.txt", "y")
    report = legacy_mirror(source, dest)
    assert report.total == 1 and report.copied == ("a.txt",)


def test_legacy_ignores_a_size_difference(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "longer\n")
    a_file(dest / "a.txt", "x\n")
    assert legacy_mirror(source, dest).copied == ("a.txt",)


def test_the_size_shortcut_says_same_for_different_bytes(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "aaaaa")
    a_file(dest / "a.txt", "bbbbb")
    assert dict(naive_size_plan(source, dest))["a.txt"] == "same"


def test_the_size_shortcut_catches_a_length_change(tmp_path):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "longer\n")
    a_file(dest / "a.txt", "x\n")
    assert dict(naive_size_plan(source, dest))["a.txt"] == "update"


def test_the_mtime_shortcut_can_be_fooled(tmp_path):
    source, dest = a_pair(tmp_path)
    original = a_file(source / "a.txt", "aaaaa")
    target = a_file(dest / "a.txt", "bbbbb")
    stamp = original.stat()
    os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert dict(naive_mtime_plan(source, dest))["a.txt"] == "same"
    assert digest(target) != digest(original)


def test_the_digest_is_not_fooled_by_a_pinned_mtime(tmp_path):
    source, dest = a_pair(tmp_path)
    original = a_file(source / "a.txt", "aaaaa")
    target = a_file(dest / "a.txt", "bbbbb")
    stamp = original.stat()
    os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert build_plan(source, dest).changes[0].action == UPDATE


# --------------------------------------------------------------------------- #
# The seeded folders
# --------------------------------------------------------------------------- #
def test_the_seeded_folders_are_the_bundled_ones():
    assert SOURCE.name == "source" and DESTINATION.name == "destination"
    assert SOURCE.parent == DESTINATION.parent


def test_the_seeded_source_holds_nine_files():
    assert len(scan_tree(SOURCE)) == 9


def test_the_seeded_destination_holds_eight_files():
    assert len(scan_tree(DESTINATION)) == 8


def test_the_seeded_source_bytes_are_pinned():
    assert sum(item.size for item in scan_tree(SOURCE).values()) == 374


def test_the_seeded_plan_counts_are_pinned():
    plan = build_plan()
    assert plan.counts() == {COPY: 4, UPDATE: 2, SKIP: 3, DELETE: 0,
                             ORPHAN: 3}


def test_the_seeded_plan_bytes_are_pinned():
    assert build_plan().bytes_to_copy == 227


def test_the_seeded_plan_hashes_are_pinned():
    assert build_plan().hashes == 13


def test_the_seeded_plan_names_its_orphans():
    assert [change.path for change in build_plan().orphans] == [
        "old/notes.bak", "old/obsolete.txt", "stray.txt"]


def test_the_seeded_points_file_is_the_same_size_on_both_sides():
    assert (SOURCE / "data" / "points.csv").stat().st_size == 17
    assert (DESTINATION / "data" / "points.csv").stat().st_size == 17
    assert digest(SOURCE / "data" / "points.csv") != \
        digest(DESTINATION / "data" / "points.csv")


def test_the_seeded_plan_is_clean():
    assert build_plan().problems() == []


def test_the_seeded_mirror_is_not_complete_yet():
    assert problems() != []


def test_the_seeded_legacy_run_counts_are_pinned():
    report = legacy_mirror()
    assert len(report.copied) == 6 and len(report.already) == 3
    assert report.hashes == 14


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


def test_demo_shows_the_two_trees(capsys):
    run_demo()
    assert "source 9 files, 374 bytes" in capsys.readouterr().out


def test_demo_shows_the_size_shortcut_failing(capsys):
    run_demo()
    assert "a size check calls it 'same'" in capsys.readouterr().out


def test_demo_shows_the_mtime_shortcut_failing(capsys):
    run_demo()
    assert "a size+mtime check says 'same', the digest says UPDATE" in \
        capsys.readouterr().out


def test_demo_shows_the_legacy_orphans(capsys):
    run_demo()
    assert "still leaves 3 extra file(s) behind" in capsys.readouterr().out


def test_demo_shows_the_delete(capsys):
    run_demo()
    assert "3/3 checks pass" in capsys.readouterr().out


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


def test_cli_prints_the_plan_by_default(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "changes      12 (4 copy, 2 update, 3 skip, 0 delete, 3 orphan)" in out
    assert "data/points.csv" in out


def test_cli_moves_nothing_by_default(capsys):
    before = sorted(scan_tree(DESTINATION))
    cli.main([])
    capsys.readouterr()
    assert sorted(scan_tree(DESTINATION)) == before


def test_cli_names_what_delete_would_remove(capsys):
    assert cli.main(["--delete"]) == 0
    out = capsys.readouterr().out
    assert "3 delete" in out and "will be deleted" in out


def test_cli_verify_fails_before_a_mirror(capsys):
    assert cli.main(["--verify"]) == 1
    out = capsys.readouterr().out
    assert "FAIL  every source file is present" in out
    assert "0/3 checks passed" in out


def test_cli_legacy(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "would copy 6 file(s)" in out
    assert "leave 3 file(s)" in out


def test_cli_report_writes_csv(tmp_path, capsys):
    target = tmp_path / "plan.csv"
    assert cli.main(["--report", str(target)]) == 0
    capsys.readouterr()
    rows = list(csv.reader(target.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == ["Action", "Path", "Bytes", "Other", "Reason"]
    assert len(rows) == 13
    assert ["update", "data/points.csv", "17", "17",
            "same size, different bytes"] in rows


def test_cli_json_writes_the_plan(tmp_path, capsys):
    target = tmp_path / "plan.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["summary"]["orphan"] == 3
    assert payload["changes"][0]["action"] == "update"
    assert payload["changes"][0]["path"] == "data/points.csv"


def test_cli_refuses_to_write_the_bundled_folders(capsys):
    assert cli.main(["--apply"]) == 2
    assert "refusing to write to the bundled folders" in capsys.readouterr().err


def test_cli_apply_needs_both_folders(tmp_path, capsys):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    assert cli.main(["--apply", "--source", str(source)]) == 2
    assert "pass --source and --target" in capsys.readouterr().err


def test_cli_apply_copies_and_reports(tmp_path, capsys):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "12345")
    assert cli.main(["--apply", "--source", str(source),
                     "--target", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "1 change(s) applied, 5 bytes copied" in out


def test_cli_apply_without_delete_exits_one_on_orphans(tmp_path, capsys):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    a_file(dest / "stale.txt", "y")
    assert cli.main(["--apply", "--source", str(source),
                     "--target", str(dest)]) == 1
    assert "the mirror still fails" in capsys.readouterr().err


def test_cli_apply_with_delete_passes_verification(tmp_path, capsys):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    a_file(dest / "stale.txt", "y")
    assert cli.main(["--apply", "--delete", "--source", str(source),
                     "--target", str(dest)]) == 0
    capsys.readouterr()
    assert problems(source, dest) == []


def test_cli_verify_after_a_mirror(tmp_path, capsys):
    source, dest = a_pair(tmp_path)
    a_file(source / "a.txt", "x")
    a_file(dest / "a.txt", "x")
    assert cli.main(["--verify", "--source", str(source),
                     "--target", str(dest)]) == 0
    assert "3/3 checks passed" in capsys.readouterr().out


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_missing_source_exits_two(capsys):
    assert cli.main(["--source", "nope"]) == 2
    assert "folder not found" in capsys.readouterr().err


def test_cli_says_nothing_to_do_for_two_empty_folders(tmp_path, capsys):
    source, dest = a_pair(tmp_path)
    assert cli.main(["--source", str(source), "--target", str(dest)]) == 0
    assert "nothing to do" in capsys.readouterr().out
