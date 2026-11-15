"""Tests for Duplicate_File_Finder: content identity, aliases and arithmetic."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
from finder import (                                          # noqa: E402
    ALGORITHM,
    CHUNK,
    DATA_DIR,
    LEGACY_IDENTITY,
    LEGACY_SKIP,
    LEGACY_STATE,
    Alias,
    DuplicateGroup,
    FindError,
    LegacyFinder,
    ScanResult,
    ScannedFile,
    digest,
    empty_digest,
    legacy_scan,
    physical_key,
    report_rows,
    report_text,
    run_demo,
    scan,
)

EMPTY = hashlib.sha256(b"").hexdigest()


def a_file(path: Path, text: str = "the same bytes\n") -> Path:
    """Write exact bytes: no \\r\\n translation, so 5 means 5."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def scanned(path: Path, size: int | None = None,
            content: str | None = None) -> ScannedFile:
    path = Path(path)
    stat = path.stat()
    return ScannedFile(path, stat.st_size if size is None else size,
                       digest(path) if content is None else content,
                       stat.st_dev, stat.st_ino)


# --------------------------------------------------------------------------- #
# digest / empty_digest
# --------------------------------------------------------------------------- #
def test_digest_is_the_sha256_of_the_bytes(tmp_path):
    target = a_file(tmp_path / "a.txt", "hello\n")
    assert digest(target) == hashlib.sha256(b"hello\n").hexdigest()


def test_digest_returns_sixty_four_hexadecimal_characters(tmp_path):
    text = digest(a_file(tmp_path / "a.txt"))
    assert len(text) == 64 and int(text, 16) >= 0


def test_digest_of_an_empty_file_is_the_digest_of_nothing(tmp_path):
    target = tmp_path / "empty.txt"
    target.write_bytes(b"")
    assert digest(target) == empty_digest()


def test_empty_digest_is_pinned():
    assert empty_digest() == \
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_empty_digest_starts_with_the_known_prefix():
    assert empty_digest().startswith("e3b0c44298fc")


def test_two_files_with_the_same_bytes_share_a_digest(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    two = a_file(tmp_path / "two.txt", "same\n")
    assert digest(one) == digest(two)


def test_one_changed_byte_changes_the_digest(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    two = a_file(tmp_path / "two.txt", "Same\n")
    assert digest(one) != digest(two)


def test_digest_reads_in_chunks_and_gives_the_same_answer(tmp_path):
    target = a_file(tmp_path / "a.txt", "x" * 5000)
    assert digest(target, chunk=7) == digest(target)


def test_digest_refuses_a_missing_file(tmp_path):
    with pytest.raises(FindError, match="no such file"):
        digest(tmp_path / "nope.txt")


def test_digest_refuses_a_directory(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(FindError, match="is a directory"):
        digest(folder)


def test_the_algorithm_is_pinned():
    assert ALGORITHM == "sha256"


def test_the_chunk_size_is_pinned():
    assert CHUNK == 65536


def test_digest_accepts_a_string_path(tmp_path):
    target = a_file(tmp_path / "a.txt", "text\n")
    assert digest(str(target)) == digest(target)


# --------------------------------------------------------------------------- #
# physical_key
# --------------------------------------------------------------------------- #
def test_a_physical_key_is_a_pair(tmp_path):
    target = a_file(tmp_path / "a.txt")
    key = physical_key(target)
    assert isinstance(key, tuple) and len(key) == 2


def test_two_paths_to_one_file_share_a_key(tmp_path):
    target = a_file(tmp_path / "a.txt", "linked\n")
    link = tmp_path / "link.txt"
    try:
        os.link(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("this filesystem has no hard links")
    assert physical_key(target) == physical_key(link)


def test_two_different_files_have_different_keys(tmp_path):
    one = a_file(tmp_path / "one.txt", "one\n")
    two = a_file(tmp_path / "two.txt", "two\n")
    assert physical_key(one) != physical_key(two)


def test_physical_key_refuses_a_missing_file(tmp_path):
    with pytest.raises(FindError, match="cannot stat"):
        physical_key(tmp_path / "nope.txt")


def test_a_symlink_resolves_to_the_key_of_its_target(tmp_path):
    target = a_file(tmp_path / "target.txt", "target\n")
    link = tmp_path / "link.txt"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow symlinks")
    assert physical_key(link) == physical_key(target)


# --------------------------------------------------------------------------- #
# ScannedFile
# --------------------------------------------------------------------------- #
def test_a_scanned_file_keeps_its_parts(tmp_path):
    target = a_file(tmp_path / "a.txt", "abc\n")
    file = scanned(target)
    assert file.path == target and file.size == 4


def test_a_scanned_file_accepts_a_string_path(tmp_path):
    target = a_file(tmp_path / "a.txt", "abc\n")
    file = ScannedFile(str(target), 4, digest(target), 0, 1)
    assert isinstance(file.path, Path)


def test_a_scanned_file_key_is_device_and_inode(tmp_path):
    target = a_file(tmp_path / "a.txt", "abc\n")
    file = scanned(target)
    assert file.key == (target.stat().st_dev, target.stat().st_ino)


def test_a_negative_size_is_refused(tmp_path):
    target = a_file(tmp_path / "a.txt", "abc\n")
    with pytest.raises(FindError, match="negative size"):
        ScannedFile(target, -1, digest(target), 0, 1)


def test_a_short_digest_is_refused(tmp_path):
    target = a_file(tmp_path / "a.txt", "abc\n")
    with pytest.raises(FindError, match="64 hexadecimal"):
        ScannedFile(target, 4, "abc", 0, 1)


def test_a_digest_that_is_not_text_is_refused(tmp_path):
    target = a_file(tmp_path / "a.txt", "abc\n")
    with pytest.raises(FindError, match="64 hexadecimal"):
        ScannedFile(target, 4, 1234, 0, 1)


def test_a_scanned_file_str_names_three_things(tmp_path):
    target = a_file(tmp_path / "report.txt", "abc\n")
    text = str(scanned(target))
    assert "report.txt" in text and "4 bytes" in text
    assert digest(target)[:12] in text


def test_a_scanned_file_dict_names_the_file_not_the_folder(tmp_path):
    target = a_file(tmp_path / "deep" / "report.txt", "abc\n")
    payload = scanned(target).to_dict()
    assert payload["path"] == "report.txt" and payload["size"] == 4


def test_a_scanned_file_is_frozen(tmp_path):
    file = scanned(a_file(tmp_path / "a.txt", "abc\n"))
    with pytest.raises(Exception):
        file.size = 9                             # type: ignore[misc]


# --------------------------------------------------------------------------- #
# DuplicateGroup
# --------------------------------------------------------------------------- #
def test_a_group_needs_two_copies(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    with pytest.raises(FindError, match="at least two copies"):
        DuplicateGroup(digest(one), 5, (one,))


def test_a_group_refuses_a_negative_size(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    with pytest.raises(FindError, match="negative size"):
        DuplicateGroup(digest(one), -1, (one, one))


def test_a_group_of_two_reclaims_one_file(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    assert DuplicateGroup(digest(one), 5, (one, one)).reclaimable == 5


def test_a_group_of_three_reclaims_two_files(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    assert DuplicateGroup(digest(one), 5,
                          (one, one, one)).reclaimable == 10


def test_an_empty_group_reclaims_nothing(tmp_path):
    one = a_file(tmp_path / "one.txt", "")
    assert DuplicateGroup(EMPTY, 0, (one, one)).reclaimable == 0


def test_a_group_dict_holds_the_names_and_the_bytes(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    two = a_file(tmp_path / "two.txt", "same\n")
    payload = DuplicateGroup(digest(one), 5, (one, two)).to_dict()
    assert payload["copies"] == ["one.txt", "two.txt"]
    assert payload["reclaimable"] == 5 and payload["size"] == 5


def test_a_group_keeps_the_digest_it_was_given(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    assert DuplicateGroup(digest(one), 5, (one, one)).digest == digest(one)


# --------------------------------------------------------------------------- #
# Alias
# --------------------------------------------------------------------------- #
def test_an_alias_reclaims_nothing(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    assert Alias(one, one).reclaimable == 0


def test_an_alias_dict_names_both_paths(tmp_path):
    one = a_file(tmp_path / "one.txt", "same\n")
    other = a_file(tmp_path / "other.txt", "same\n")
    payload = Alias(other, one).to_dict()
    assert payload == {"path": "other.txt", "kept": "one.txt"}


# --------------------------------------------------------------------------- #
# ScanResult
# --------------------------------------------------------------------------- #
def a_result(tmp_path, folder: str = "files") -> ScanResult:
    return scan(a_file(tmp_path / folder / "keep.txt", "same\n").parent)


def test_a_new_result_can_be_empty(tmp_path):
    result = ScanResult(tmp_path, [], [], [])
    assert len(result) == 0 and result.groups == ()
    assert result.reclaimable == 0 and result.duplicate_files == 0


def test_the_length_counts_paths_not_groups(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    assert len(scan(root)) == 2


def test_iteration_walks_the_groups(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    assert [group.size for group in scan(root)] == [5]


def test_repr_reports_the_three_numbers(tmp_path):
    result = a_result(tmp_path)
    assert repr(result) == ("<ScanResult 1 files, 0 duplicate groups, "
                            "0 bytes reclaimable>")


def test_physical_files_are_the_ones_that_hold_bytes(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    result = scan(root)
    assert len(result.physical) == 2 and result.aliases == ()


def test_total_bytes_sums_the_physical_files(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "12345")
    a_file(root / "two.txt", "12345")
    assert scan(root).total_bytes == 10


def test_by_digest_names_every_group(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    result = scan(root)
    assert list(result.by_digest()) == [group.digest for group in result.groups]


def test_the_summary_holds_every_count(tmp_path):
    result = a_result(tmp_path)
    assert result.summary() == {"root": "files", "paths": 1, "files": 1,
                               "aliases": 0, "groups": 0, "duplicate_files": 0,
                               "bytes": 5, "reclaimable": 0}


def test_to_dict_holds_the_summary_groups_and_aliases(tmp_path):
    payload = a_result(tmp_path).to_dict()
    assert set(payload) == {"summary", "groups", "aliases"}


def test_verify_returns_four_checks(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    checks = scan(root).verify()
    assert len(checks) == 4 and all(passed for _, passed in checks)


def test_a_clean_result_has_no_problems(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    assert scan(root).problems() == []


def test_verify_catches_a_copy_that_no_longer_agrees(tmp_path):
    root = tmp_path / "files"
    one = a_file(root / "one.txt", "aaaaa")
    two = a_file(root / "two.txt", "bbbbb")
    group = DuplicateGroup(digest(one), 5, (one, two))
    result = ScanResult(root, [scanned(one), scanned(two)], [], [group])
    assert result.problems() == ["every copy in a group hashes the same"]


def test_verify_catches_a_group_with_one_file(tmp_path):
    root = tmp_path / "files"
    one = a_file(root / "one.txt", "same\n")
    group = DuplicateGroup(digest(one), 5, (one, one))
    object.__setattr__(group, "copies", (one,))
    result = ScanResult(root, [scanned(one)], [], [group])
    assert result.problems() == ["no group holds a single file"]


def test_verify_catches_a_wrong_group_size(tmp_path):
    root = tmp_path / "files"
    one = a_file(root / "one.txt", "same\n")
    two = a_file(root / "two.txt", "same\n")
    group = DuplicateGroup(digest(one), 5, (one, two))
    object.__setattr__(group, "size", 6)
    result = ScanResult(root, [scanned(one), scanned(two)], [], [group])
    assert result.problems() == ["every copy in a group has its size"]


def test_verify_catches_a_wrong_group_digest(tmp_path):
    root = tmp_path / "files"
    one = a_file(root / "one.txt", "same\n")
    two = a_file(root / "two.txt", "same\n")
    group = DuplicateGroup(EMPTY, 5, (one, two))
    result = ScanResult(root, [scanned(one), scanned(two)], [], [group])
    assert result.problems() == \
        ["every group's first copy still hashes to its digest"]


def test_verify_names_its_checks(tmp_path):
    result = a_result(tmp_path)
    assert [name for name, _ in result.verify()] == [
        "every group's first copy still hashes to its digest",
        "every copy in a group hashes the same",
        "every copy in a group has its size",
        "no group holds a single file"]


def test_verify_is_repeatable(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    result = scan(root)
    assert result.verify() == result.verify()


# --------------------------------------------------------------------------- #
# scan
# --------------------------------------------------------------------------- #
def test_scan_refuses_a_missing_folder(tmp_path):
    with pytest.raises(FindError, match="folder not found"):
        scan(tmp_path / "nope")


def test_scan_refuses_a_file(tmp_path):
    target = a_file(tmp_path / "a.txt")
    with pytest.raises(FindError, match="is a file, not a folder"):
        scan(target)


def test_scan_of_an_empty_folder_finds_nothing(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    result = scan(root)
    assert len(result) == 0 and result.groups == ()


def test_scan_groups_two_identical_files(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    result = scan(root)
    assert len(result.groups) == 1 and len(result.groups[0].copies) == 2


def test_scan_keeps_equal_sizes_apart_when_the_bytes_differ(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "aaaaa")
    a_file(root / "two.txt", "bbbbb")
    result = scan(root)
    assert result.groups == () and result.reclaimable == 0


def test_scan_groups_three_copies(tmp_path):
    root = tmp_path / "files"
    for name in ("a.txt", "b.txt", "c.txt"):
        a_file(root / name, "same\n")
    result = scan(root)
    assert len(result.groups[0].copies) == 3
    assert result.duplicate_files == 2 and result.reclaimable == 10


def test_scan_groups_the_empty_files(tmp_path):
    root = tmp_path / "files"
    (root / "a.txt").parent.mkdir(parents=True)
    (root / "a.txt").write_bytes(b"")
    (root / "b.txt").write_bytes(b"")
    result = scan(root)
    assert len(result.groups) == 1 and result.groups[0].size == 0
    assert result.groups[0].digest == EMPTY


def test_scan_orders_groups_by_size_then_digest(tmp_path):
    root = tmp_path / "files"
    a_file(root / "small1.txt", "ab")
    a_file(root / "small2.txt", "ab")
    a_file(root / "big1.txt", "abcdefgh")
    a_file(root / "big2.txt", "abcdefgh")
    assert [group.size for group in scan(root)] == [8, 2]


def test_scan_orders_the_copies_by_name(tmp_path):
    root = tmp_path / "files"
    a_file(root / "zeta.txt", "same\n")
    a_file(root / "alpha.txt", "same\n")
    assert [path.name for path in scan(root).groups[0].copies] == \
        ["alpha.txt", "zeta.txt"]


def test_scan_walks_into_subfolders(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "deep" / "two.txt", "same\n")
    assert len(scan(root).groups) == 1


def test_scan_ignores_a_folder_that_only_looks_like_a_file(tmp_path):
    root = tmp_path / "files"
    (root / "one.txt").mkdir(parents=True)
    assert len(scan(root)) == 0


def test_a_hard_link_is_an_alias_not_a_copy(tmp_path):
    root = tmp_path / "files"
    original = a_file(root / "original.txt", "the same bytes\n")
    link = root / "linked.txt"
    try:
        os.link(original, link)
    except (OSError, NotImplementedError):
        pytest.skip("this filesystem has no hard links")
    result = scan(root)
    assert result.groups == () and result.reclaimable == 0
    assert len(result.aliases) == 1
    alias = result.aliases[0]
    assert {alias.path, alias.kept} == {original, link}
    assert alias.path != alias.kept
    assert alias.reclaimable == 0


def test_an_alias_is_not_counted_as_physical_bytes(tmp_path):
    root = tmp_path / "files"
    original = a_file(root / "original.txt", "12345")
    link = root / "linked.txt"
    try:
        os.link(original, link)
    except (OSError, NotImplementedError):
        pytest.skip("this filesystem has no hard links")
    result = scan(root)
    assert len(result) == 2 and len(result.physical) == 1
    assert result.total_bytes == 5 and result.summary()["aliases"] == 1


def test_a_second_scan_returns_the_same_value(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    assert scan(root).to_dict() == scan(root).to_dict()


def test_scan_takes_the_chunk_size(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "x" * 300)
    a_file(root / "two.txt", "x" * 300)
    assert scan(root, chunk=9).to_dict() == scan(root).to_dict()


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def test_report_rows_number_the_groups(tmp_path):
    result = a_result(tmp_path)
    assert report_rows(result) == []


def test_report_rows_describe_each_group(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    rows = report_rows(scan(root))
    assert rows[0]["group"] == 1 and rows[0]["copies"] == 2
    assert rows[0]["files"] == ["one.txt", "two.txt"]
    assert rows[0]["digest"] == digest(root / "one.txt")[:12]


def test_report_text_starts_with_its_header(tmp_path):
    assert report_text(a_result(tmp_path)).splitlines()[0] == \
        "Group,Digest,Bytes,Copies,Reclaimable,Files"


def test_report_text_ends_with_a_newline(tmp_path):
    assert report_text(a_result(tmp_path)).endswith("\n")


def test_report_text_holds_one_line_per_group(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    assert len(report_text(scan(root)).splitlines()) == 2


def test_report_text_names_the_bytes(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    assert ",5,2,5," in report_text(scan(root))


# --------------------------------------------------------------------------- #
# The legacy project
# --------------------------------------------------------------------------- #
def test_the_legacy_constants_are_the_three_defects():
    assert LEGACY_SKIP == "if file.stat().st_size == 0: continue"
    assert LEGACY_STATE == "self.duplicates.setdefault(file_hash, []).append(file)"
    assert LEGACY_IDENTITY == "file"


def test_legacy_scan_skips_every_empty_file(tmp_path):
    root = tmp_path / "files"
    (root / "a.txt").parent.mkdir(parents=True)
    (root / "a.txt").write_bytes(b"")
    (root / "b.txt").write_bytes(b"")
    assert legacy_scan([root / "a.txt", root / "b.txt"]) == {}


def test_legacy_scan_finds_ordinary_duplicates(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    found = legacy_scan([root / "one.txt", root / "two.txt"])
    assert len(found) == 1 and len(list(found.values())[0]) == 1


def test_legacy_scan_calls_a_hard_link_a_duplicate(tmp_path):
    root = tmp_path / "files"
    original = a_file(root / "original.txt", "linked\n")
    link = root / "linked.txt"
    try:
        os.link(original, link)
    except (OSError, NotImplementedError):
        pytest.skip("this filesystem has no hard links")
    assert len(legacy_scan([original, link])) == 1


def test_a_legacy_finder_that_is_called_twice_keeps_its_state(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    paths = [root / "one.txt", root / "two.txt"]
    finder = LegacyFinder()
    first = finder.scan_files(paths)
    assert sum(len(members) for members in first.values()) == 1
    second = finder.scan_files(paths)
    assert sum(len(members) for members in second.values()) == 3


def test_a_second_legacy_scan_calls_a_unique_file_a_duplicate(tmp_path):
    root = tmp_path / "files"
    unique = a_file(root / "unique.txt", "alone\n")
    finder = LegacyFinder()
    finder.scan_files([unique])
    assert finder.scan_files([unique]) != {}


def test_the_legacy_reclaimable_counts_every_listed_duplicate(tmp_path):
    root = tmp_path / "files"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    finder = LegacyFinder()
    finder.scan_files([root / "one.txt", root / "two.txt"])
    assert finder.reclaimable == 5


# --------------------------------------------------------------------------- #
# The seeded folder
# --------------------------------------------------------------------------- #
def test_the_data_folder_is_the_bundled_one():
    assert DATA_DIR.name == "files" and DATA_DIR.parent.name == "data"


def test_the_seeded_folder_holds_eight_paths():
    assert len(scan()) == 8


def test_the_seeded_folder_holds_eight_physical_files():
    assert len(scan().physical) == 8


def test_the_seeded_folder_has_three_groups():
    assert len(scan().groups) == 3


def test_the_seeded_folder_has_three_deletable_copies():
    assert scan().duplicate_files == 3


def test_the_seeded_reclaimable_bytes_are_pinned():
    assert scan().reclaimable == 343


def test_the_seeded_total_bytes_are_pinned():
    assert scan().total_bytes == 972


def test_the_seeded_sizes_are_pinned():
    assert sorted({file.size for file in scan().files}) == [0, 75, 170, 173,
                                                            211]


def test_the_seeded_group_sizes_are_pinned():
    assert [group.size for group in scan().groups] == [173, 170, 0]


def test_the_seeded_folder_is_clean():
    assert scan().problems() == []


def test_the_seeded_folder_has_no_aliases():
    assert scan().aliases == ()


def test_the_seeded_empty_pair_is_one_group():
    groups = [group for group in scan().groups if group.size == 0]
    assert len(groups) == 1 and len(groups[0].copies) == 2
    assert groups[0].digest == EMPTY


def test_the_seeded_unique_files_are_alone():
    names = {path.name for group in scan().groups for path in group.copies}
    assert "budget.csv" not in names and "unique.txt" not in names


def test_the_seeded_report_has_four_lines():
    assert len(report_text(scan()).splitlines()) == 4


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


def test_demo_shows_the_seeded_counts(capsys):
    run_demo()
    assert "8 paths, 8 files, 3 duplicate groups, 3 deletable copies" in \
        capsys.readouterr().out


def test_demo_shows_the_size_buckets(capsys):
    run_demo()
    assert "the 8 files have 5 distinct sizes" in capsys.readouterr().out


def test_demo_shows_the_empty_group(capsys):
    run_demo()
    assert "the two empty files are one group of 2" in capsys.readouterr().out


def test_demo_shows_the_empty_digest(capsys):
    run_demo()
    assert "e3b0c44298fc" in capsys.readouterr().out


def test_demo_shows_the_hard_link(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "hard link" in out and "reclaims 0 bytes" in out


def test_demo_shows_the_legacy_doubling(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "a second call lists 8" in out


def test_demo_shows_the_reclaimable_arithmetic(capsys):
    run_demo()
    assert "170 + 173 + 0 = 343 bytes" in capsys.readouterr().out


def test_demo_shows_the_legacy_bytes(capsys):
    run_demo()
    assert "implies 1315 bytes" in capsys.readouterr().out


def test_demo_shows_the_verification(capsys):
    run_demo()
    assert "4/4 checks pass after re-reading" in capsys.readouterr().out


def test_demo_shows_the_second_scan(capsys):
    run_demo()
    assert "3 groups both times" in capsys.readouterr().out


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


def test_cli_prints_a_summary_by_default(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "paths        8" in out and "reclaimable  343 bytes" in out


def test_cli_lists_the_groups_by_default(capsys):
    assert cli.main([]) == 0
    assert "group 1: 173 bytes each" in capsys.readouterr().out


def test_cli_summary_only(capsys):
    assert cli.main(["--summary"]) == 0
    out = capsys.readouterr().out
    assert "groups       3 duplicate group(s)" in out
    assert "group 1:" not in out


def test_cli_duplicates_only(capsys):
    assert cli.main(["--duplicates"]) == 0
    out = capsys.readouterr().out
    assert "empty-b.txt" in out and "paths" not in out


def test_cli_verify(capsys):
    assert cli.main(["--verify"]) == 0
    out = capsys.readouterr().out
    assert "PASS  every copy in a group hashes the same" in out
    assert "4/4 checks passed" in out


def test_cli_legacy(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "empty files it never looked at: empty-a.txt, empty-b.txt" in out
    assert "the same finder called a second time: 8 duplicate(s)" in out
    assert "this module: 3 deletable copy(ies) and 343 reclaimable bytes" in out


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--summary", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_report_writes_csv(tmp_path, capsys):
    target = tmp_path / "out.csv"
    assert cli.main(["--report", str(target)]) == 0
    assert target.read_text(encoding="utf-8").startswith("Group,Digest,")
    assert "wrote 3 group(s)" in capsys.readouterr().out


def test_cli_report_creates_directories(tmp_path, capsys):
    target = tmp_path / "a" / "b" / "out.csv"
    assert cli.main(["--report", str(target)]) == 0
    capsys.readouterr()
    assert target.is_file()


def test_cli_json_writes_the_scan(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["summary"]["groups"] == 3
    assert payload["summary"]["reclaimable"] == 343
    assert payload["groups"][0]["copies"] == ["notes-backup.txt", "notes.txt"]


def test_cli_json_is_valid_ascii(tmp_path, capsys):
    target = tmp_path / "out.json"
    cli.main(["--json", str(target)])
    capsys.readouterr()
    assert all(ord(character) < 128
               for character in target.read_text(encoding="utf-8"))


def test_cli_missing_folder_exits_two(capsys):
    assert cli.main(["--folder", "no-such-folder"]) == 2
    assert "folder not found" in capsys.readouterr().err


def test_cli_scans_another_folder(tmp_path, capsys):
    root = tmp_path / "other"
    a_file(root / "one.txt", "same\n")
    a_file(root / "two.txt", "same\n")
    assert cli.main(["--folder", str(root), "--duplicates"]) == 0
    assert "group 1: 5 bytes each, 2 copies" in capsys.readouterr().out


def test_cli_reports_no_groups(tmp_path, capsys):
    root = tmp_path / "other"
    a_file(root / "one.txt", "one\n")
    assert cli.main(["--folder", str(root), "--duplicates"]) == 0
    assert "no duplicate groups" in capsys.readouterr().out


def test_cli_quiet_still_exits_two_on_a_bad_folder(capsys):
    assert cli.main(["--folder", "nope", "--quiet"]) == 2
    assert "folder not found" in capsys.readouterr().err


def test_the_human_formatter_keeps_small_numbers_in_bytes():
    assert cli._human(0) == "0 B" and cli._human(1023) == "1023 B"


def test_the_human_formatter_scales_thousands():
    assert cli._human(1024) == "1.0 KB" and cli._human(1536) == "1.5 KB"


def test_the_human_formatter_scales_millions():
    assert cli._human(1024 ** 2) == "1.0 MB"


def test_the_human_formatter_scales_billions():
    assert cli._human(1024 ** 3) == "1.0 GB"
